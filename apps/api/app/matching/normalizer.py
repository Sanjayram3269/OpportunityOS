"""Skill normalization — maps variant skill names to canonical forms.

The normalizer is deliberately small and maintainable.  It handles:
  - case folding
  - whitespace normalization
  - common abbreviations (JS → JavaScript, TS → TypeScript)
  - common aliases (ML → Machine Learning, AI → Artificial Intelligence)
  - separator normalization (FastAPI → fastapi, Node.js → nodejs)

To extend: add entries to ``_ALIASES`` or ``_SEPARATOR_RULES``.
"""

from __future__ import annotations

import re
import unicodedata

# ── Alias table ───────────────────────────────────────────────────────────
# Maps a lowercased, stripped variant → canonical lowercase form.
# Keep this list short and intentional.

_ALIASES: dict[str, str] = {
    # Programming languages
    "js": "javascript",
    "ts": "typescript",
    "python3": "python",
    "py": "python",
    "rb": "ruby",
    "rs": "rust",
    "cs": "c#",
    "csharp": "c#",
    "cpp": "c++",
    "c++": "c++",
    "golang": "go",
    "kt": "kotlin",
    "objc": "objective-c",
    "swift": "swift",
    "php": "php",
    "r": "r",
    "scala": "scala",
    "dart": "dart",
    "lua": "lua",
    "perl": "perl",
    # Frameworks / tools
    "fast api": "fastapi",
    "node js": "nodejs",
    "node.js": "nodejs",
    "vue js": "vuejs",
    "vue.js": "vuejs",
    "next js": "nextjs",
    "next.js": "nextjs",
    "nuxt js": "nuxtjs",
    "nuxt.js": "nuxtjs",
    "react js": "reactjs",
    "react.js": "reactjs",
    "angular js": "angularjs",
    "angular.js": "angularjs",
    "express js": "expressjs",
    "express.js": "expressjs",
    "deno": "deno",
    "tailwind css": "tailwindcss",
    "tailwind": "tailwindcss",
    "three js": "threejs",
    "three.js": "threejs",
    # Databases
    "postgres": "postgresql",
    "psql": "postgresql",
    "mysql": "mysql",
    "sqlite": "sqlite",
    "mongo": "mongodb",
    "mongo db": "mongodb",
    "mongo-db": "mongodb",
    "redis": "redis",
    "elasticsearch": "elasticsearch",
    "elastic search": "elasticsearch",
    "dynamo db": "dynamodb",
    "dynamo-db": "dynamodb",
    "cosmos db": "cosmosdb",
    "cosmos-db": "cosmosdb",
    # Cloud / DevOps
    "aws": "amazon web services",
    "amazon web services": "amazon web services",
    "gcp": "google cloud platform",
    "google cloud": "google cloud platform",
    "azure": "microsoft azure",
    "microsoft azure": "microsoft azure",
    "k8s": "kubernetes",
    "docker": "docker",
    "ci/cd": "ci cd",
    "github actions": "github actions",
    "gitlab ci": "gitlab ci",
    "terraform": "terraform",
    "ansible": "ansible",
    "jenkins": "jenkins",
    # AI / ML
    "ml": "machine learning",
    "machine learning": "machine learning",
    "ai": "artificial intelligence",
    "artificial intelligence": "artificial intelligence",
    "dl": "deep learning",
    "deep learning": "deep learning",
    "nlp": "natural language processing",
    "natural language processing": "natural language processing",
    "cv": "computer vision",
    "computer vision": "computer vision",
    "llm": "large language model",
    "large language model": "large language model",
    "gen ai": "generative ai",
    "generative ai": "generative ai",
    "gen ai": "generative ai",
    "mlops": "mlops",
    "data science": "data science",
    "data engineering": "data engineering",
    "data analytics": "data analytics",
    "data analysis": "data analysis",
    # Soft / general
    "agile": "agile",
    "scrum": "scrum",
    "rest": "rest api",
    "rest api": "rest api",
    "restful": "rest api",
    "graphql": "graphql",
    "grpc": "grpc",
    "gRPC": "grpc",
    "websocket": "websocket",
    "web socket": "websocket",
    "microservices": "microservices",
    "micro services": "microservices",
    "serverless": "serverless",
    "saas": "saas",
    "paas": "paas",
    "iaas": "iaas",
}


# ── Separator normalization ───────────────────────────────────────────────

def _normalize_separator(name: str) -> str:
    """Replace common separators with a canonical form."""
    # Replace dots, hyphens, underscores, plus signs with nothing
    # (e.g. "Node.js" → "nodejs", "C++" → "cpp" via alias, "CI/CD" → "ci cd")
    name = re.sub(r"[./_+]", "", name)
    return name


# ── Public API ────────────────────────────────────────────────────────────

_WS_RE = re.compile(r"\s+")


def normalize_skill(raw: str) -> str:
    """Normalize a skill name to a canonical lowercase form.

    Examples::

        >>> normalize_skill("Python")
        'python'
        >>> normalize_skill("JS")
        'javascript'
        >>> normalize_skill("FastAPI")
        'fastapi'
        >>> normalize_skill("Machine Learning")
        'machine learning'
        >>> normalize_skill("PostgreSQL")
        'postgresql'
    """
    # 1. Unicode normalize + lowercase + strip
    name = unicodedata.normalize("NFKC", raw).lower().strip()

    # 2. Collapse whitespace
    name = _WS_RE.sub(" ", name)

    # 3. Alias lookup BEFORE separator normalization
    #    (e.g. "CI/CD" → "ci cd" via alias, not "cicd" via separator strip)
    if name in _ALIASES:
        return _ALIASES[name]

    # 4. Separator normalization
    name = _normalize_separator(name)

    # 5. Try alias again after separator normalization
    if name in _ALIASES:
        return _ALIASES[name]

    # 6. Return the cleaned name as-is if no alias found
    return name


def normalize_skills(raw_skills: list[str]) -> set[str]:
    """Normalize a list of skill names and return a set of canonical forms."""
    return {normalize_skill(s) for s in raw_skills if s and s.strip()}


# ── Text-based skill extraction ───────────────────────────────────────────

# Common tech keywords that appear in descriptions/titles.
# This is NOT an exhaustive list — it's a lightweight signal extractor.
_TECH_KEYWORDS: list[str] = [
    # Languages
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust",
    "ruby", "php", "swift", "kotlin", "scala", "dart", "lua", "perl", "r",
    "html", "css", "sql",
    # Frameworks
    "react", "angular", "vue", "nextjs", "nuxtjs", "svelte",
    "fastapi", "django", "flask", "express", "spring", "rails",
    "nodejs", "deno", "bun",
    # Data / ML
    "pandas", "numpy", "scipy", "scikit-learn", "sklearn",
    "tensorflow", "pytorch", "keras", "huggingface",
    "machine learning", "deep learning", "artificial intelligence",
    "nlp", "computer vision", "data science", "data engineering",
    "spark", "hadoop", "kafka", "airflow",
    # Cloud / DevOps
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
    "jenkins", "github actions", "gitlab ci",
    # Databases
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "dynamodb", "cosmosdb", "sqlite",
    # Tools
    "git", "linux", "bash", "graphql", "rest", "grpc", "websocket",
    "figma", "tailwindcss", "sass",
]


def extract_skills_from_text(text: str) -> set[str]:
    """Extract normalized skill mentions from free-form text.

    This is a lightweight keyword-based extractor, not an NLP parser.
    It catches common tech keywords mentioned in descriptions.
    Returns canonical normalized forms (e.g. 'aws' → 'amazon web services').
    """
    if not text:
        return set()

    text_lower = text.lower()
    found: set[str] = set()

    for keyword in _TECH_KEYWORDS:
        # Use word boundary matching to avoid false positives
        # e.g. "go" shouldn't match "going", but "go " or "Go," should
        pattern = r"(?:^|[\s,;(])" + re.escape(keyword) + r"(?:$|[\s,;)..])"
        if re.search(pattern, text_lower):
            # Normalize each keyword through the alias system
            found.add(normalize_skill(keyword))

    return found
