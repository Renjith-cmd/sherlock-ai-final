"""Legitimate built-in transforms for DNS, network infrastructure, and file hashing."""

import dns.resolver
import hashlib
import re
from typing import List, Dict, Any
from urllib.parse import urlparse
from src.core.models import Entity, EntityType, TransformResultCandidate
from src.core.transforms import BaseTransform, TransformMetadata, registry


class DnsToIpTransform(BaseTransform):
    metadata = TransformMetadata(
        id="dns_resolve_a_record",
        name="Resolve Domain to IPv4 (A)",
        description="Queries live DNS A records to discover associated IPv4 addresses.",
        category="Network Infrastructure",
        accepted_types=[EntityType.DOMAIN],
        output_types=[EntityType.IP],
        requires_credentials=False,
        is_local=False,
    )

    async def execute(self, entity: Entity, config: Dict[str, Any] = None) -> List[TransformResultCandidate]:
        domain = entity.label.strip().lower()
        candidates: List[TransformResultCandidate] = []
        try:
            answers = dns.resolver.resolve(domain, "A", lifetime=5.0)
            for rdata in answers:
                ip_str = str(rdata)
                candidates.append(
                    TransformResultCandidate(
                        entity_type=EntityType.IP,
                        label=ip_str,
                        properties={"ip_version": 4, "record_type": "A"},
                        relationship_type="RESOLVES_TO",
                        confidence=1.0,
                        evidence={"raw_answer": ip_str, "resolver": "system_dns"}
                    )
                )
        except Exception as e:
            # Return empty if nxdomain or timeout, preserving resilience
            pass
        return candidates


class DnsToMxTransform(BaseTransform):
    metadata = TransformMetadata(
        id="dns_resolve_mx_record",
        name="Find Mail Servers (MX)",
        description="Queries live DNS MX records to discover mail exchange domain names.",
        category="Network Infrastructure",
        accepted_types=[EntityType.DOMAIN],
        output_types=[EntityType.DOMAIN],
        requires_credentials=False,
        is_local=False,
    )

    async def execute(self, entity: Entity, config: Dict[str, Any] = None) -> List[TransformResultCandidate]:
        domain = entity.label.strip().lower()
        candidates: List[TransformResultCandidate] = []
        try:
            answers = dns.resolver.resolve(domain, "MX", lifetime=5.0)
            for rdata in answers:
                mx_host = str(rdata.exchange).rstrip(".")
                candidates.append(
                    TransformResultCandidate(
                        entity_type=EntityType.DOMAIN,
                        label=mx_host,
                        properties={"preference": rdata.preference, "record_type": "MX"},
                        relationship_type="MAIL_SERVER",
                        confidence=1.0,
                        evidence={"preference": rdata.preference, "raw_host": mx_host}
                    )
                )
        except Exception:
            pass
        return candidates


class UrlToDomainTransform(BaseTransform):
    metadata = TransformMetadata(
        id="url_extract_domain",
        name="Extract Domain from URL",
        description="Parses a URL string and extracts its canonical host/domain name.",
        category="Web Analysis",
        accepted_types=[EntityType.URL],
        output_types=[EntityType.DOMAIN],
        requires_credentials=False,
        is_local=True,
    )

    async def execute(self, entity: Entity, config: Dict[str, Any] = None) -> List[TransformResultCandidate]:
        url = entity.label.strip()
        candidates: List[TransformResultCandidate] = []
        parsed = urlparse(url if "://" in url else f"http://{url}")
        host = parsed.netloc.split(":")[0].strip().lower()
        if host:
            candidates.append(
                TransformResultCandidate(
                    entity_type=EntityType.DOMAIN,
                    label=host,
                    properties={"scheme": parsed.scheme, "path": parsed.path},
                    relationship_type="HOSTED_ON",
                    confidence=1.0,
                    evidence={"parsed_url": url, "extracted_host": host}
                )
            )
        return candidates


class EmailToDomainTransform(BaseTransform):
    metadata = TransformMetadata(
        id="email_extract_domain",
        name="Extract Domain from Email",
        description="Extracts the email service domain from an email address.",
        category="Identity & Contact",
        accepted_types=[EntityType.EMAIL],
        output_types=[EntityType.DOMAIN],
        requires_credentials=False,
        is_local=True,
    )

    async def execute(self, entity: Entity, config: Dict[str, Any] = None) -> List[TransformResultCandidate]:
        email = entity.label.strip()
        candidates: List[TransformResultCandidate] = []
        if "@" in email:
            domain = email.split("@")[-1].strip().lower()
            if domain:
                candidates.append(
                    TransformResultCandidate(
                        entity_type=EntityType.DOMAIN,
                        label=domain,
                        properties={"user": email.split("@")[0]},
                        relationship_type="EMAIL_DOMAIN",
                        confidence=1.0,
                        evidence={"source_email": email}
                    )
                )
        return candidates


def register_standard_transforms():
    registry.register(DnsToIpTransform())
    registry.register(DnsToMxTransform())
    registry.register(UrlToDomainTransform())
    registry.register(EmailToDomainTransform())


register_standard_transforms()
