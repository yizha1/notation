// Copyright The Notary Project Authors.
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"crypto"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"encoding/base64"
	"testing"

	"github.com/golang-jwt/jwt/v4"
	"github.com/notaryproject/notation-core-go/signature"
)

func TestSignJWTCompatibility(t *testing.T) {
	rsaKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	tests := []struct {
		algorithm signature.Algorithm
		curve     elliptic.Curve
	}{
		{algorithm: signature.AlgorithmPS256},
		{algorithm: signature.AlgorithmPS384},
		{algorithm: signature.AlgorithmPS512},
		{algorithm: signature.AlgorithmES256, curve: elliptic.P256()},
		{algorithm: signature.AlgorithmES384, curve: elliptic.P384()},
		{algorithm: signature.AlgorithmES512, curve: elliptic.P521()},
	}
	for _, tt := range tests {
		name, err := toJWTAlgorithm(tt.algorithm)
		if err != nil {
			t.Fatal(err)
		}
		t.Run(name, func(t *testing.T) {
			var key crypto.Signer = rsaKey
			if tt.curve != nil {
				ecdsaKey, err := ecdsa.GenerateKey(tt.curve, rand.Reader)
				if err != nil {
					t.Fatal(err)
				}
				key = ecdsaKey
			}
			raw, err := sign("test payload", key, tt.algorithm)
			if err != nil {
				t.Fatal(err)
			}
			if err := jwt.GetSigningMethod(name).Verify(
				"test payload", base64.RawURLEncoding.EncodeToString(raw), key.Public(),
			); err != nil {
				t.Fatalf("signature does not round-trip after JWT update: %v", err)
			}
		})
	}
}
