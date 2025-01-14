# Introduction

The dubbing-service provides the following functionality:
* Receives files and creates a priortized queue to serve them
* Notifies by email when file is ready or it has been error

# Running the system locally using Docker

This requires that you have *docker*, *docker-compose* and *make* installed in your system.

First build by running:

```shell
 make build-all
```

Once the system is built, you can run it typing:

```shell
make docker-run
```

And open http://localhost:8700/stats to verify that the service works.

Also in the [html-client](html-client) directory you have a simple HTML client to test the service.


# Contact

Email address: Jordi Mas: jmas@softcatala.org

