"""Email provider abstraction — channel-agnostic email delivery.

This package provides:
  - EmailProvider base class
  - SMTP provider implementation
  - DeliveryResult dataclass

Email sending is OPTIONAL. If not configured, the system still works.
"""
