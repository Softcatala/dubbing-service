import sys


import os
import datetime as dt
from pathlib import Path
import torch
import numpy as np
import soundfile as sf
import argparse

sys.path.append("..")
sys.path.append("Matcha-TTS/")

# Vocos imports
from vocos import Vocos

# Matcha imports
from matcha.models.matcha_tts import MatchaTTS
from matcha.text import sequence_to_text, text_to_sequence
from matcha.utils.utils import get_user_data_dir, intersperse

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


MULTIACCENT_MODEL = "projecte-aina/matxa-tts-cat-multiaccent"
DEFAULT_CLEANER = "catalan_cleaners"


def get_cleaner_for_speaker_id(speaker_id):
    speaker_cleaner_mapping = {
        0: "catalan_balear_cleaners",
        1: "catalan_balear_cleaners",
        2: "catalan_cleaners",
        3: "catalan_cleaners",
        4: "catalan_occidental_cleaners",
        5: "catalan_occidental_cleaners",
        6: "catalan_valencia_cleaners",
        7: "catalan_valencia_cleaners",
    }

    return speaker_cleaner_mapping.get(speaker_id, DEFAULT_CLEANER)


def load_model_from_hf(matcha_hf, device):
    model = MatchaTTS.from_pretrained(matcha_hf, device=device)
    return model


count_params = lambda x: f"{sum(p.numel() for p in x.parameters()):,}"


def load_vocos_vocoder_from_hf(vocos_hf, device):
    vocos = Vocos.from_pretrained(vocos_hf, device=device)
    return vocos


def load_models():
    matxa = "projecte-aina/matxa-tts-cat-multiaccent"
    alvocat = "projecte-aina/alvocat-vocos-22khz"

    model = load_model_from_hf(matxa, device=device).to(device)
    vocos_vocoder = load_vocos_vocoder_from_hf(alvocat, device=device).to(device)
    return model, vocos_vocoder


@torch.inference_mode()
def process_text(text: str, cleaner: str):
    x = torch.tensor(
        intersperse(text_to_sequence(text, [cleaner]), 0),
        dtype=torch.long,
        device=device,
    )[None]
    x_lengths = torch.tensor([x.shape[-1]], dtype=torch.long, device=device)
    x_phones = sequence_to_text(x.squeeze(0).tolist())
    return {"x_orig": text, "x": x, "x_lengths": x_lengths, "x_phones": x_phones}


@torch.inference_mode()
def synthesise(text, spks, n_timesteps, temperature, length_scale, cleaner, model):
    text_processed = process_text(text, cleaner)
    start_t = dt.datetime.now()
    output = model.synthesise(
        text_processed["x"],
        text_processed["x_lengths"],
        n_timesteps=n_timesteps,
        temperature=temperature,
        spks=spks,
        length_scale=length_scale,
    )
    # merge everything to one dict
    output.update({"start_t": start_t, **text_processed})
    return output


@torch.inference_mode()
def to_vocos_waveform(mel, vocoder):
    audio = vocoder.decode(mel).cpu().squeeze()
    return audio


def save_to_folder(filename: str, output: dict):
    sf.write(filename, output["waveform"], 22050, "PCM_24")


def tts(
    text,
    spk_id,
    n_timesteps=10,
    length_scale=1.0,
    temperature=0.70,
    output_filename=None,
    cleaner="catalan_cleaners",
    model=None,
    vocos_vocoder=None,
):
    n_spk = (
        torch.tensor([spk_id], device=device, dtype=torch.long) if spk_id >= 0 else None
    )
    outputs, rtfs = [], []
    rtfs_w = []

    output = synthesise(
        text, n_spk, n_timesteps, temperature, length_scale, cleaner, model=model
    )
    output["waveform"] = to_vocos_waveform(output["mel"], vocos_vocoder)

    # Compute Real Time Factor (RTF) with Vocoder
    t = (dt.datetime.now() - output["start_t"]).total_seconds()
    rtf_w = t * 22050 / (output["waveform"].shape[-1])

    rtfs.append(output["rtf"])
    rtfs_w.append(rtf_w)

    # Save the generated waveform
    save_to_folder(output_filename, output)
