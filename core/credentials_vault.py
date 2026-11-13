"""
Credentials Vault Module - Aayushifty CloudDesk
Integrates natively with Windows Credential Manager (Win32 Credential API).
Guarantees zero plain-text storage in configuration files, Git repositories, or logs.
"""
from __future__ import annotations

import win32cred
from typing import Any, Dict, List, Optional

VAULT_PREFIX = "AayushiftyCloudDesk"

PROVIDER_URLS = {
    "GEMINI_API_KEY": {
        "name": "Google Gemini API Key",
        "url": "https://aistudio.google.com/app/apikey",
        "desc": "Official Google AI Studio API Key generator (Free tier available)."
    },
    "OPENAI_API_KEY": {
        "name": "OpenAI API Key",
        "url": "https://platform.openai.com/api-keys",
        "desc": "OpenAI Platform API keys for GPT models."
    },
    "HF_TOKEN": {
        "name": "Hugging Face User Access Token",
        "url": "https://huggingface.co/settings/tokens",
        "desc": "Hugging Face token for downloading gated models and datasets."
    },
    "GITHUB_TOKEN": {
        "name": "GitHub Personal Access Token",
        "url": "https://github.com/settings/tokens",
        "desc": "Fine-grained or classic personal access token for GitHub operations."
    }
}


class CredentialsVault:
    """Interacts securely with Windows Credential Manager for API keys and tokens."""

    @staticmethod
    def _build_target_name(key_name: str) -> str:
        clean_key = key_name.strip().upper()
        return f"{VAULT_PREFIX}/{clean_key}"

    @classmethod
    def store_secret(cls, key_name: str, secret_value: str) -> bool:
        """Stores a secret securely inside the Windows Credential Manager."""
        if not key_name or not secret_value:
            return False

        target = cls._build_target_name(key_name)
        credential = {
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": target,
            "UserName": key_name.strip().upper(),
            "CredentialBlob": secret_value.strip(),
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
            "Comment": "Managed securely by Aayushifty CloudDesk"
        }

        try:
            win32cred.CredWrite(credential, 0)
            return True
        except Exception as e:
            # Never print or log the secret!
            return False

    @classmethod
    def get_secret(cls, key_name: str) -> Optional[str]:
        """Retrieves a secret from Windows Credential Manager."""
        target = cls._build_target_name(key_name)
        try:
            cred = win32cred.CredRead(target, win32cred.CRED_TYPE_GENERIC, 0)
            blob = cred["CredentialBlob"]
            if isinstance(blob, bytes):
                try:
                    return blob.decode("utf-16-le")
                except Exception:
                    return blob.decode("utf-8", errors="ignore")
            return str(blob)
        except Exception:
            return None

    @classmethod
    def delete_secret(cls, key_name: str) -> bool:
        """Deletes a secret from Windows Credential Manager."""
        target = cls._build_target_name(key_name)
        try:
            win32cred.CredDelete(target, win32cred.CRED_TYPE_GENERIC, 0)
            return True
        except Exception:
            return False

    @classmethod
    def list_keys(cls) -> List[Dict[str, Any]]:
        """
        Lists stored keys with masked values for UI display.
        NEVER reveals complete secret values in logs or UI responses.
        """
        results = []
        for key_code, meta in PROVIDER_URLS.items():
            secret = cls.get_secret(key_code)
            has_secret = secret is not None and len(secret) > 0
            masked = ""
            if has_secret:
                if len(secret) > 8:
                    masked = f"{secret[:3]}••••••••{secret[-4:]}"
                else:
                    masked = "••••••••"

            results.append({
                "key_code": key_code,
                "name": meta["name"],
                "url": meta["url"],
                "desc": meta["desc"],
                "configured": has_secret,
                "masked_preview": masked
            })

        return results

