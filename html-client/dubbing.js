
// https://api.softcatala.org/dubbing-service/v1/
var URL='http://localhost:8700'

var HttpClient = function() {
    this.get = function(aUrl, aCallback) {
        var anHttpRequest = new XMLHttpRequest();
        anHttpRequest.onreadystatechange = function() { 
            if (anHttpRequest.readyState == 4 && anHttpRequest.status == 200)
                aCallback(anHttpRequest.responseText);
        }

        anHttpRequest.open( "GET", aUrl, true );
        anHttpRequest.send( null );
    }
}


function sendFile()
{
    var xmlHttp = new XMLHttpRequest();
        xmlHttp.onreadystatechange = function()
        {
            if(xmlHttp.readyState != 4)
            {
                return;
            }

            if (xmlHttp.status == 200)
            {
                var jsonResponse = JSON.parse(xmlHttp.responseText);
                var uuid = jsonResponse['uuid'];
                element = document.getElementById('download-dub');
                element.innerText = uuid;
                element.href = URL + `/get_file?uuid=` + uuid + `&ext=dub`;
            }
            else
            {
                json = JSON.parse(xmlHttp.responseText);
                alert(json['error']);
            }
        }

        var formData = new FormData(document.getElementById('form-id'));
        url = URL + `/dubbing_file/`;
        xmlHttp.open("post", url);
        xmlHttp.send(formData); 
}
