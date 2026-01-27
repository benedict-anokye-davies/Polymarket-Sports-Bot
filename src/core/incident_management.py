"""
PagerDuty and OpsGenie alerting integration.
Provides incident management and on-call escalation.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


logger = logging.getLogger(__name__)


class IncidentSeverity(str, Enum):
    """Incident severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IncidentStatus(str, Enum):
    """Incident status values."""
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass
class Incident:
    """Represents an incident."""
    title: str
    description: str
    severity: IncidentSeverity
    source: str
    component: str | None = None
    group: str | None = None
    custom_details: dict = field(default_factory=dict)
    dedup_key: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "source": self.source,
            "component": self.component,
            "group": self.group,
            "custom_details": self.custom_details,
            "dedup_key": self.dedup_key,
            "timestamp": self.timestamp.isoformat(),
        }


class AlertingProvider(ABC):
    """Abstract base class for alerting providers."""
    
    @abstractmethod
    async def create_incident(self, incident: Incident) -> str | None:
        """Create an incident. Returns incident ID or None on failure."""
        pass
    
    @abstractmethod
    async def acknowledge_incident(self, incident_id: str) -> bool:
        """Acknowledge an incident."""
        pass
    
    @abstractmethod
    async def resolve_incident(self, incident_id: str, resolution: str | None = None) -> bool:
        """Resolve an incident."""
        pass


class PagerDutyProvider(AlertingProvider):
    """
    PagerDuty alerting integration.
    
    Uses the Events API v2 for incident management.
    """
    
    EVENTS_API_URL = "https://events.pagerduty.com/v2/enqueue"
    
    SEVERITY_MAPPING = {
        IncidentSeverity.CRITICAL: "critical",
        IncidentSeverity.HIGH: "error",
        IncidentSeverity.MEDIUM: "warning",
        IncidentSeverity.LOW: "warning",
        IncidentSeverity.INFO: "info",
    }
    
    def __init__(self, routing_key: str, source: str = "polymarket-bot"):
        """
        Initialize PagerDuty provider.
        
        Args:
            routing_key: PagerDuty integration/routing key
            source: Default source identifier
        """
        self._routing_key = routing_key
        self._source = source
    
    async def create_incident(self, incident: Incident) -> str | None:
        """Create a PagerDuty incident."""
        try:
            import httpx
            
            payload = {
                "routing_key": self._routing_key,
                "event_action": "trigger",
                "dedup_key": incident.dedup_key,
                "payload": {
                    "summary": incident.title,
                    "source": incident.source or self._source,
                    "severity": self.SEVERITY_MAPPING.get(
                        incident.severity, "warning"
                    ),
                    "timestamp": incident.timestamp.isoformat(),
                    "component": incident.component,
                    "group": incident.group,
                    "custom_details": {
                        "description": incident.description,
                        **incident.custom_details,
                    },
                },
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.EVENTS_API_URL,
                    json=payload,
                    timeout=30.0,
                )
                
                if response.status_code == 202:
                    data = response.json()
                    return data.get("dedup_key")
                else:
                    logger.error(f"PagerDuty error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to create PagerDuty incident: {e}")
            return None
    
    async def acknowledge_incident(self, incident_id: str) -> bool:
        """Acknowledge a PagerDuty incident."""
        return await self._send_event("acknowledge", incident_id)
    
    async def resolve_incident(self, incident_id: str, resolution: str | None = None) -> bool:
        """Resolve a PagerDuty incident."""
        return await self._send_event("resolve", incident_id, resolution)
    
    async def _send_event(
        self,
        action: str,
        dedup_key: str,
        resolution: str | None = None,
    ) -> bool:
        """Send an event action to PagerDuty."""
        try:
            import httpx
            
            payload = {
                "routing_key": self._routing_key,
                "event_action": action,
                "dedup_key": dedup_key,
            }
            
            if resolution:
                payload["payload"] = {
                    "summary": resolution,
                    "source": self._source,
                    "severity": "info",
                }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.EVENTS_API_URL,
                    json=payload,
                    timeout=30.0,
                )
                
                return response.status_code == 202
                
        except Exception as e:
            logger.error(f"Failed to {action} PagerDuty incident: {e}")
            return False


class OpsGenieProvider(AlertingProvider):
    """
    OpsGenie alerting integration.
    
    Uses the Alert API for incident management.
    """
    
    API_URL = "https://api.opsgenie.com/v2/alerts"
    
    PRIORITY_MAPPING = {
        IncidentSeverity.CRITICAL: "P1",
        IncidentSeverity.HIGH: "P2",
        IncidentSeverity.MEDIUM: "P3",
        IncidentSeverity.LOW: "P4",
        IncidentSeverity.INFO: "P5",
    }
    
    def __init__(self, api_key: str, source: str = "polymarket-bot"):
        """
        Initialize OpsGenie provider.
        
        Args:
            api_key: OpsGenie API key
            source: Default source identifier
        """
        self._api_key = api_key
        self._source = source
    
    async def create_incident(self, incident: Incident) -> str | None:
        """Create an OpsGenie alert."""
        try:
            import httpx
            
            payload = {
                "message": incident.title,
                "description": incident.description,
                "priority": self.PRIORITY_MAPPING.get(incident.severity, "P3"),
                "source": incident.source or self._source,
                "alias": incident.dedup_key,
                "details": incident.custom_details,
            }
            
            if incident.component:
                payload["entity"] = incident.component
            
            headers = {
                "Authorization": f"GenieKey {self._api_key}",
                "Content-Type": "application/json",
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.API_URL,
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )
                
                if response.status_code in (200, 202):
                    data = response.json()
                    return data.get("requestId")
                else:
                    logger.error(f"OpsGenie error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to create OpsGenie alert: {e}")
            return None
    
    async def acknowledge_incident(self, incident_id: str) -> bool:
        """Acknowledge an OpsGenie alert."""
        try:
            import httpx
            
            url = f"{self.API_URL}/{incident_id}/acknowledge"
            headers = {
                "Authorization": f"GenieKey {self._api_key}",
                "Content-Type": "application/json",
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={"source": self._source},
                    headers=headers,
                    timeout=30.0,
                )
                
                return response.status_code in (200, 202)
                
        except Exception as e:
            logger.error(f"Failed to acknowledge OpsGenie alert: {e}")
            return False
    
    async def resolve_incident(self, incident_id: str, resolution: str | None = None) -> bool:
        """Close an OpsGenie alert."""
        try:
            import httpx
            
            url = f"{self.API_URL}/{incident_id}/close"
            headers = {
                "Authorization": f"GenieKey {self._api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {"source": self._source}
            if resolution:
                payload["note"] = resolution
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )
                
                return response.status_code in (200, 202)
                
        except Exception as e:
            logger.error(f"Failed to close OpsGenie alert: {e}")
            return False


class SlackAlertingProvider(AlertingProvider):
    """
    Slack alerting integration.
    
    Uses incoming webhooks for notifications.
    Does not support acknowledge/resolve natively.
    """
    
    SEVERITY_COLORS = {
        IncidentSeverity.CRITICAL: "#FF0000",
        IncidentSeverity.HIGH: "#FF6600",
        IncidentSeverity.MEDIUM: "#FFCC00",
        IncidentSeverity.LOW: "#00FF00",
        IncidentSeverity.INFO: "#0066FF",
    }
    
    def __init__(self, webhook_url: str, channel: str | None = None):
        """
        Initialize Slack provider.
        
        Args:
            webhook_url: Slack incoming webhook URL
            channel: Optional channel override
        """
        self._webhook_url = webhook_url
        self._channel = channel
    
    async def create_incident(self, incident: Incident) -> str | None:
        """Post incident to Slack."""
        try:
            import httpx
            
            attachment = {
                "color": self.SEVERITY_COLORS.get(incident.severity, "#808080"),
                "title": f"[{incident.severity.value.upper()}] {incident.title}",
                "text": incident.description,
                "fields": [
                    {"title": "Source", "value": incident.source, "short": True},
                    {"title": "Severity", "value": incident.severity.value, "short": True},
                ],
                "footer": "Polymarket Trading Bot",
                "ts": int(incident.timestamp.timestamp()),
            }
            
            if incident.component:
                attachment["fields"].append({
                    "title": "Component",
                    "value": incident.component,
                    "short": True,
                })
            
            if incident.custom_details:
                for key, value in list(incident.custom_details.items())[:5]:
                    attachment["fields"].append({
                        "title": key,
                        "value": str(value)[:100],
                        "short": True,
                    })
            
            payload = {"attachments": [attachment]}
            if self._channel:
                payload["channel"] = self._channel
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._webhook_url,
                    json=payload,
                    timeout=30.0,
                )
                
                if response.status_code == 200:
                    return incident.dedup_key or str(incident.timestamp.timestamp())
                else:
                    logger.error(f"Slack error: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to post to Slack: {e}")
            return None
    
    async def acknowledge_incident(self, incident_id: str) -> bool:
        """Slack doesn't support native acknowledgment."""
        return True
    
    async def resolve_incident(self, incident_id: str, resolution: str | None = None) -> bool:
        """Post resolution message to Slack."""
        if not resolution:
            return True
        
        try:
            import httpx
            
            payload = {
                "attachments": [{
                    "color": "#00FF00",
                    "title": "Incident Resolved",
                    "text": resolution,
                    "footer": f"Incident ID: {incident_id}",
                }]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._webhook_url,
                    json=payload,
                    timeout=30.0,
                )
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Failed to post resolution to Slack: {e}")
            return False


class IncidentManager:
    """
    Manages incidents across multiple alerting providers.
    
    Handles deduplication, escalation, and status tracking.
    """
    
    def __init__(self):
        self._providers: list[AlertingProvider] = []
        self._active_incidents: dict[str, Incident] = {}
        self._lock = asyncio.Lock()
    
    def add_provider(self, provider: AlertingProvider) -> None:
        """Add an alerting provider."""
        self._providers.append(provider)
    
    async def trigger(self, incident: Incident) -> list[str]:
        """
        Trigger an incident across all providers.
        
        Returns:
            List of incident IDs from providers
        """
        async with self._lock:
            # Check for duplicate
            dedup_key = incident.dedup_key
            if dedup_key and dedup_key in self._active_incidents:
                logger.debug(f"Duplicate incident suppressed: {dedup_key}")
                return []
            
            # Create incident on all providers
            results = await asyncio.gather(
                *[p.create_incident(incident) for p in self._providers],
                return_exceptions=True,
            )
            
            incident_ids = [r for r in results if isinstance(r, str)]
            
            if dedup_key and incident_ids:
                self._active_incidents[dedup_key] = incident
            
            return incident_ids
    
    async def acknowledge(self, dedup_key: str) -> bool:
        """Acknowledge an incident."""
        async with self._lock:
            if dedup_key not in self._active_incidents:
                return False
            
            results = await asyncio.gather(
                *[p.acknowledge_incident(dedup_key) for p in self._providers],
                return_exceptions=True,
            )
            
            return any(r is True for r in results)
    
    async def resolve(self, dedup_key: str, resolution: str | None = None) -> bool:
        """Resolve an incident."""
        async with self._lock:
            if dedup_key not in self._active_incidents:
                return False
            
            results = await asyncio.gather(
                *[p.resolve_incident(dedup_key, resolution) for p in self._providers],
                return_exceptions=True,
            )
            
            if any(r is True for r in results):
                del self._active_incidents[dedup_key]
                return True
            
            return False
    
    def get_active_incidents(self) -> list[Incident]:
        """Get all active incidents."""
        return list(self._active_incidents.values())


# Global incident manager
incident_manager = IncidentManager()


def setup_incident_management(
    pagerduty_key: str | None = None,
    opsgenie_key: str | None = None,
    slack_webhook: str | None = None,
) -> IncidentManager:
    """
    Setup incident management with configured providers.
    
    Args:
        pagerduty_key: PagerDuty routing key
        opsgenie_key: OpsGenie API key
        slack_webhook: Slack webhook URL
    
    Returns:
        Configured IncidentManager
    """
    if pagerduty_key:
        incident_manager.add_provider(PagerDutyProvider(pagerduty_key))
    
    if opsgenie_key:
        incident_manager.add_provider(OpsGenieProvider(opsgenie_key))
    
    if slack_webhook:
        incident_manager.add_provider(SlackAlertingProvider(slack_webhook))
    
    return incident_manager
