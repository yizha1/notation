module github.com/notaryproject/notation/test/e2e

go 1.26.0

require (
	github.com/notaryproject/notation-core-go v1.3.0
	github.com/notaryproject/notation-go v1.3.2
	github.com/onsi/ginkgo/v2 v2.28.1
	github.com/onsi/gomega v1.39.0
	github.com/opencontainers/image-spec v1.1.1
	oras.land/oras-go/v2 v2.6.2
)

require (
	github.com/Masterminds/semver/v3 v3.4.0 // indirect
	github.com/fxamacker/cbor/v2 v2.9.4 // indirect
	github.com/go-logr/logr v1.4.3 // indirect
	github.com/go-task/slim-sprig/v3 v3.0.0 // indirect
	github.com/google/go-cmp v0.7.0 // indirect
	github.com/google/pprof v0.0.0-20260115054156-294ebfa9ad83 // indirect
	github.com/notaryproject/tspclient-go v1.0.1-0.20250306063739-4f55b14d9f01 // indirect
	github.com/opencontainers/go-digest v1.0.0 // indirect
	github.com/veraison/go-cose v1.3.0 // indirect
	github.com/x448/float16 v0.8.4 // indirect
	go.yaml.in/yaml/v3 v3.0.4 // indirect
	golang.org/x/crypto v0.57.0 // indirect
	golang.org/x/mod v0.41.0 // indirect
	golang.org/x/net v0.58.0 // indirect
	golang.org/x/sync v0.23.0 // indirect
	golang.org/x/sys v0.48.0 // indirect
	golang.org/x/text v0.42.0 // indirect
	golang.org/x/tools v0.49.0 // indirect
)

replace github.com/notaryproject/notation/test/e2e/plugin => ./plugin

replace github.com/notaryproject/notation-core-go => github.com/yizha1/notation-core-go v1.3.1-trial.4

replace github.com/notaryproject/notation-go => github.com/yizha1/notation-go v1.3.3-trial.2
