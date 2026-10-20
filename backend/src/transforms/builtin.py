"""Legitimate built-in transforms for DNS, RDAP, Network Infrastructure, and Document Analysis."""

import dns.resolver
import dns.reversename
import hashlib
import re
from typing import List, Dict, Any
from urllib.parse import urlparse
import httpx

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
        except Exception:
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


class DnsToNsTransform(BaseTransform):
    metadata = TransformMetadata(
        id="dns_resolve_ns_record",
        name="Find Nameservers (NS)",
        description="Queries authoritative DNS nameserver records for the domain.",
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
            answers = dns.resolver.resolve(domain, "NS", lifetime=5.0)
            for rdata in answers:
                ns_host = str(rdata.target).rstrip(".")
                candidates.append(
                    TransformResultCandidate(
                        entity_type=EntityType.DOMAIN,
                        label=ns_host,
                        properties={"record_type": "NS"},
                        relationship_type="NAMESERVER",
                        confidence=1.0,
                        evidence={"raw_host": ns_host}
                    )
                )
        except Exception:
            pass
        return candidates


class IpReverseDnsTransform(BaseTransform):
    metadata = TransformMetadata(
        id="ip_reverse_dns_ptr",
        name="Reverse DNS Lookup (PTR)",
        description="Performs reverse DNS PTR lookup to discover the host name assigned to this IP.",
        category="Network Infrastructure",
        accepted_types=[EntityType.IP],
        output_types=[EntityType.DOMAIN],
        requires_credentials=False,
        is_local=False,
    )

    async def execute(self, entity: Entity, config: Dict[str, Any] = None) -> List[TransformResultCandidate]:
        ip_addr = entity.label.strip()
        candidates: List[TransformResultCandidate] = []
        try:
            rev_name = dns.reversename.from_address(ip_addr)
            answers = dns.resolver.resolve(rev_name, "PTR", lifetime=5.0)
            for rdata in answers:
                ptr_host = str(rdata.target).rstrip(".")
                candidates.append(
                    TransformResultCandidate(
                        entity_type=EntityType.DOMAIN,
                        label=ptr_host,
                        properties={"record_type": "PTR"},
                        relationship_type="REVERSE_PTR",
                        confidence=1.0,
                        evidence={"ip": ip_addr, "ptr_host": ptr_host}
                    )
                )
        except Exception:
            pass
        return candidates


class RdapWhoisTransform(BaseTransform):
    metadata = TransformMetadata(
        id="rdap_whois_lookup",
        name="RDAP / Registration Authority Lookup",
        description="Queries public Registration Data Access Protocol (RDAP) servers for network/domain ownership.",
        category="Attribution & Ownership",
        accepted_types=[EntityType.IP, EntityType.DOMAIN],
        output_types=[EntityType.ORGANIZATION],
        requires_credentials=False,
        is_local=False,
    )

    async def execute(self, entity: Entity, config: Dict[str, Any] = None) -> List[TransformResultCandidate]:
        val = entity.label.strip().lower()
        candidates: List[TransformResultCandidate] = []
        try:
            url = f"https://rdap.arin.net/registry/ip/{val}" if entity.type == EntityType.IP else f"https://rdap.org/domain/{val}"
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                res = await client.get(url, headers={"Accept": "application/rdap+json, application/json"})
                if res.status_code == 200:
                    data = res.json()
                    name = data.get("name") or data.get("handle")
                    if name:
                        candidates.append(
                            TransformResultCandidate(
                                entity_type=EntityType.ORGANIZATION,
                                label=str(name),
                                properties={"handle": data.get("handle"), "country": data.get("country")},
                                relationship_type="REGISTERED_TO",
                                confidence=0.95,
                                evidence={"rdap_endpoint": url, "name": name}
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


class TextEntityExtractorTransform(BaseTransform):
    metadata = TransformMetadata(
        id="text_extract_entities",
        name="Extract Indicators from Document Text",
        description="Extracts embedded IP addresses, domains, and email addresses from document contents or text notes.",
        category="Document Intelligence",
        accepted_types=[EntityType.DOCUMENT, EntityType.CUSTOM],
        output_types=[EntityType.DOMAIN, EntityType.IP, EntityType.EMAIL],
        requires_credentials=False,
        is_local=True,
    )

    async def execute(self, entity: Entity, config: Dict[str, Any] = None) -> List[TransformResultCandidate]:
        # Inspect label or properties['content']
        text = str(entity.properties.get("content") or entity.label)
        candidates: List[TransformResultCandidate] = []

        # Find emails
        emails = set(re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", text))
        for em in emails:
            candidates.append(
                TransformResultCandidate(
                    entity_type=EntityType.EMAIL,
                    label=em.lower(),
                    relationship_type="MENTIONED_IN",
                    confidence=0.9,
                    evidence={"matched_pattern": "email_regex"}
                )
            )

        # Find IPv4 addresses
        ips = set(re.findall(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", text))
        for ip in ips:
            candidates.append(
                TransformResultCandidate(
                    entity_type=EntityType.IP,
                    label=ip,
                    relationship_type="MENTIONED_IN",
                    confidence=0.9,
                    evidence={"matched_pattern": "ipv4_regex"}
                )
            )

        return candidates


def register_standard_transforms():
    registry.register(DnsToIpTransform())
    registry.register(DnsToMxTransform())
    registry.register(DnsToNsTransform())
    registry.register(IpReverseDnsTransform())
    registry.register(RdapWhoisTransform())
    registry.register(UrlToDomainTransform())
    registry.register(EmailToDomainTransform())
    registry.register(TextEntityExtractorTransform())


register_standard_transforms()
