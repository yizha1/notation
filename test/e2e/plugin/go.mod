module github.com/notaryproject/notation/test/e2e/plugin

go 1.26.0

require (
	github.com/golang-jwt/jwt/v4 v4.5.2
	github.com/notaryproject/notation-core-go v1.3.0
	github.com/notaryproject/notation-go v1.3.2
	github.com/notaryproject/notation-plugin-framework-go v1.0.0
	github.com/spf13/cobra v1.10.2
)

require (
	github.com/Azure/go-ntlmssp v0.1.1 // indirect
	github.com/fxamacker/cbor/v2 v2.9.4 // indirect
	github.com/go-asn1-ber/asn1-ber v1.5.8 // indirect
	github.com/go-ldap/ldap/v3 v3.4.14 // indirect
	github.com/google/uuid v1.6.0 // indirect
	github.com/inconshreveable/mousetrap v1.1.0 // indirect
	github.com/notaryproject/tspclient-go v1.0.1-0.20250306063739-4f55b14d9f01 // indirect
	github.com/opencontainers/go-digest v1.0.0 // indirect
	github.com/opencontainers/image-spec v1.1.1 // indirect
	github.com/spf13/pflag v1.0.10 // indirect
	github.com/veraison/go-cose v1.3.0 // indirect
	github.com/x448/float16 v0.8.4 // indirect
	golang.org/x/crypto v0.57.0 // indirect
	golang.org/x/mod v0.41.0 // indirect
	golang.org/x/sync v0.22.0 // indirect
	oras.land/oras-go/v2 v2.6.2 // indirect
)

replace github.com/notaryproject/notation-core-go => github.com/yizha1/notation-core-go v1.3.2-monthly-test.202610

replace github.com/notaryproject/notation-go => github.com/yizha1/notation-go v1.3.4-monthly-test.202610
