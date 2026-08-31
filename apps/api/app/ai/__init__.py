"""AI Intelligence Layer — optional enrichment on top of deterministic matching.

This package provides:
  - AIProvider abstraction (base class for swapping providers)
  - Prompt templates for structured AI insight generation
  - HuggingFace / OpenRouter free-model providers

The deterministic matching engine remains the source of truth for scores.
AI only enriches with explanations, strengths, gaps, and recommendations.
"""
