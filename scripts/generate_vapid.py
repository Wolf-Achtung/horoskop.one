#!/usr/bin/env python3
"""VAPID-Schlüsselpaar für Web-Push erzeugen.

Einmal lokal ausführen, die beiden Werte als Railway-Variablen setzen:
    VAPID_PRIVATE_KEY  (geheim halten!)
    VAPID_PUBLIC_KEY
Optional: VAPID_SUBJECT (mailto:…), PUSH_TIME (HH:MM, Europe/Berlin),
PUSH_STORE_PATH (auf ein Railway-Volume zeigen, damit Abos Deploys überleben).
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


key = ec.generate_private_key(ec.SECP256R1())
private_value = key.private_numbers().private_value.to_bytes(32, "big")
public_point = key.public_key().public_bytes(
    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)

print("VAPID_PRIVATE_KEY=" + b64url(private_value))
print("VAPID_PUBLIC_KEY=" + b64url(public_point))
