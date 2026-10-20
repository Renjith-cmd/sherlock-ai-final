"""Entity validation, canonical normalization, and type schema definitions."""

import re
import ipaddress
from urllib.parse import urlparse
from typing import Tuple, Dict, Any
from src.core.models import EntityType


class ValidationError(Exception):
    pass


def normalize_and_validate_entity(entity_type: EntityType, label: str, properties: Dict[str, Any] = None) -> Tuple[str, Dict[str, Any]]:
    raw = label.strip()
    props = dict(properties or {})

    if not raw:
        raise ValidationError("Entity label cannot be empty.")

    if entity_type == EntityType.DOMAIN:
        # Strip scheme or path if user pasted full URL into domain
        cleaned = raw.lower()
        if "://" in cleaned:
            cleaned = urlparse(cleaned).netloc
        cleaned = cleaned.split(":")[0].strip().rstrip(".")
        if not re.match(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$", cleaned):
            raise ValidationError(f"Invalid domain format: '{raw}'")
        props["canonical_domain"] = cleaned
        return cleaned, props

    elif entity_type == EntityType.IP:
        cleaned = raw.split(":")[0].strip()
        try:
            ip_obj = ipaddress.ip_address(cleaned)
            props["is_private"] = ip_obj.is_private
            props["is_global"] = ip_obj.is_global
            props["version"] = ip_obj.version
            return str(ip_obj), props
        except ValueError:
            raise ValidationError(f"Invalid IPv4/IPv6 address: '{raw}'")

    elif entity_type == EntityType.EMAIL:
        cleaned = raw.lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", cleaned):
            raise ValidationError(f"Invalid email format: '{raw}'")
        user, domain = cleaned.split("@", 1)
        props["username"] = user
        props["domain"] = domain
        return cleaned, props

    elif entity_type == EntityType.URL:
        if not (raw.startswith("http://") or raw.startswith("https://") or raw.startswith("ftp://")):
            raw = f"https://{raw}"
        parsed = urlparse(raw)
        if not parsed.netloc:
            raise ValidationError(f"Invalid URL structure: '{raw}'")
        props["scheme"] = parsed.scheme
        props["hostname"] = parsed.netloc
        props["path"] = parsed.path
        return raw, props

    elif entity_type == EntityType.FILE_HASH:
        cleaned = raw.lower()
        hex_pattern = r"^[a-f0-9]+$"
        if not re.match(hex_pattern, cleaned):
            raise ValidationError("File hash must be hexadecimal characters only.")
        length = len(cleaned)
        if length == 32:
            props["hash_algorithm"] = "MD5"
        elif length == 40:
            props["hash_algorithm"] = "SHA-1"
        elif length == 64:
            props["hash_algorithm"] = "SHA-256"
        elif length == 128:
            props["hash_algorithm"] = "SHA-512"
        else:
            raise ValidationError(f"Unsupported hash length ({length} characters). Must be MD5, SHA-1, SHA-256, or SHA-512.")
        return cleaned, props

    elif entity_type == EntityType.PHONE:
        cleaned = re.sub(r"[\s\-\(\)]", "", raw)
        if not re.match(r"^\+?[0-9]{7,15}$", cleaned):
            raise ValidationError(f"Invalid telephone number: '{raw}'")
        return cleaned, props

    # Person, Organization, Location, Document, Custom
    return raw, props
