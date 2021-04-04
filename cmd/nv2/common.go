package main

import "github.com/urfave/cli/v2"

var (
	usernameFlag = &cli.StringFlag{
		Name:    "username",
		Aliases: []string{"u"},
		Usage:   "username for generic remote access",
		EnvVars: []string{"NV2_USERNAME"},
	}
	passwordFlag = &cli.StringFlag{
		Name:    "password",
		Aliases: []string{"p"},
		Usage:   "password for generic remote access",
		EnvVars: []string{"NV2_PASSWORD"},
	}
	plainHTTPFlag = &cli.BoolFlag{
		Name:  "plain-http",
		Usage: "remote access via plain HTTP",
	}
	mediaTypeFlag = &cli.StringFlag{
		Name:  "media-type",
		Usage: "specify the media type of the manifest read from file or stdin",
		Value: "application/vnd.docker.distribution.manifest.v2+json",
	}
	outputFlag = &cli.StringFlag{
		Name:    "output",
		Aliases: []string{"o"},
		Usage:   "write signature to a specific path",
	}
)
