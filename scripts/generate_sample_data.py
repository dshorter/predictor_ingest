#!/usr/bin/env python3
"""Generate realistic sample graph data at different scale tiers.

Usage:
    python scripts/generate_sample_data.py              # all tiers
    python scripts/generate_sample_data.py medium       # single tier
    python scripts/generate_sample_data.py large stress  # multiple tiers

Output goes to web/data/graphs/{tier}/ with 4 view files each.
"""

import json
import os
import random
import sys
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_BASE = os.path.join(PROJECT_ROOT, "web", "data", "graphs")

SEED = 42
DATE_END = datetime(2026, 1, 25)
DATE_START = datetime(2025, 10, 25)  # ~90 day range

# ---------------------------------------------------------------------------
# Realistic entity pools — names, aliases, types
# ---------------------------------------------------------------------------

ORGS = [
    ("OpenAI", ["Open AI"]),
    ("Anthropic", []),
    ("Google DeepMind", ["DeepMind", "Google AI"]),
    ("Meta AI", ["FAIR", "Meta"]),
    ("Microsoft Research", ["MSR", "Microsoft"]),
    ("Mistral AI", ["Mistral"]),
    ("Stability AI", ["Stability"]),
    ("Cohere", []),
    ("AI2", ["Allen Institute for AI"]),
    ("Nvidia", ["NVIDIA"]),
    ("Amazon AWS", ["AWS", "Amazon"]),
    ("Apple ML", ["Apple Machine Learning"]),
    ("Hugging Face", ["HF"]),
    ("xAI", []),
    ("Inflection AI", ["Inflection"]),
    ("Databricks", []),
    ("Scale AI", ["Scale"]),
    ("Runway ML", ["Runway"]),
    ("Midjourney", []),
    ("Character AI", ["Character.AI"]),
    ("Salesforce AI", ["Salesforce Research"]),
    ("IBM Research", ["IBM"]),
    ("Samsung AI", ["Samsung Research"]),
    ("Baidu AI", ["Baidu"]),
    ("Tencent AI", ["Tencent"]),
    ("ByteDance AI", ["ByteDance"]),
    ("Alibaba DAMO", ["DAMO Academy", "Alibaba AI"]),
    ("01.AI", []),
    ("Adept AI", ["Adept"]),
    ("Aleph Alpha", []),
]

PEOPLE = [
    ("Sam Altman", []),
    ("Dario Amodei", []),
    ("Demis Hassabis", []),
    ("Yann LeCun", ["Y. LeCun"]),
    ("Ilya Sutskever", []),
    ("Andrej Karpathy", []),
    ("Arthur Mensch", []),
    ("Emad Mostaque", []),
    ("Aidan Gomez", []),
    ("Jensen Huang", []),
    ("Percy Liang", []),
    ("Fei-Fei Li", []),
    ("Jeff Dean", []),
    ("Mira Murati", []),
    ("Jan Leike", []),
    ("Chris Olah", []),
    ("Daniela Amodei", []),
    ("Greg Brockman", []),
    ("Noam Shazeer", []),
    ("Yi Tay", []),
]

MODELS = [
    ("GPT-5", ["GPT 5", "gpt-5"]),
    ("Claude Opus 4.5", ["Opus 4.5", "Claude Opus"]),
    ("Gemini Ultra 2", ["Gemini 2", "Gemini Ultra"]),
    ("Llama 4", ["LLaMA 4", "Llama-4"]),
    ("Mixtral 8x22B", ["Mixtral-8x22B"]),
    ("Command R+", ["Command R Plus"]),
    ("DALL-E 4", ["DALLE 4"]),
    ("Stable Diffusion 4", ["SD4", "SD 4"]),
    ("Whisper v4", ["Whisper V4"]),
    ("Codex 2", []),
    ("PaLM 3", ["PaLM3"]),
    ("Phi-4", ["Phi 4"]),
    ("Grok-3", ["Grok 3"]),
    ("Qwen-3", ["Qwen3", "Qwen 3"]),
    ("Yi-Large", ["Yi Large"]),
    ("DeepSeek-V3", ["DeepSeek V3"]),
    ("Falcon 3", ["Falcon3"]),
    ("Jamba 2", []),
    ("Nemotron-5", ["Nemotron 5"]),
    ("Aya 3", []),
    ("Sora 2", ["Sora V2"]),
    ("Midjourney V7", ["MJ V7"]),
    ("Claude Sonnet 4", ["Sonnet 4"]),
    ("GPT-4o Mini 2", ["GPT4o Mini 2"]),
    ("Gemma 3", ["Gemma3"]),
]

TOOLS = [
    ("LangChain", []),
    ("LlamaIndex", ["Llama Index"]),
    ("AutoGPT", ["Auto-GPT"]),
    ("CrewAI", []),
    ("Haystack", []),
    ("Semantic Kernel", []),
    ("Weights & Biases", ["W&B", "wandb"]),
    ("MLflow", []),
    ("vLLM", []),
    ("TensorRT-LLM", ["TensorRT LLM"]),
    ("Ollama", []),
    ("LocalAI", []),
    ("LiteLLM", []),
    ("Gradio", []),
    ("Streamlit", []),
    ("Cursor", []),
    ("Copilot", ["GitHub Copilot"]),
    ("Cody", ["Sourcegraph Cody"]),
    ("Dify", []),
    ("Flowise", []),
]

DATASETS = [
    ("Common Crawl", []),
    ("The Pile", ["Pile"]),
    ("RedPajama v2", ["RedPajama"]),
    ("FineWeb", []),
    ("LAION-5B", ["LAION"]),
    ("SlimPajama", []),
    ("Dolma", []),
    ("StarCoder Data", []),
    ("The Stack v2", ["The Stack"]),
    ("RefinedWeb", []),
    ("ROOTS", []),
    ("OpenWebText2", ["OWT2"]),
    ("C4", ["Colossal Clean Crawled Corpus"]),
    ("Wikipedia Dump 2025", ["Wikipedia"]),
    ("mC4", []),
]

BENCHMARKS = [
    ("MMLU", ["Massive Multitask Language Understanding"]),
    ("GPQA", ["Graduate-Level Google-Proof QA"]),
    ("HumanEval", ["Human Eval"]),
    ("MATH", []),
    ("GSM8K", []),
    ("ARC-AGI", ["ARC AGI"]),
    ("HellaSwag", []),
    ("TruthfulQA", []),
    ("MT-Bench", ["MTBench"]),
    ("AlpacaEval 2", ["AlpacaEval"]),
    ("LMSYS Chatbot Arena", ["Chatbot Arena"]),
    ("SWE-bench", ["SWE Bench"]),
    ("BigBench Hard", ["BBH"]),
    ("WinoGrande", []),
    ("MBPP", []),
]

TECH = [
    ("Transformer Architecture", ["Transformers"]),
    ("Mixture of Experts", ["MoE"]),
    ("RLHF", ["Reinforcement Learning from Human Feedback"]),
    ("DPO", ["Direct Preference Optimization"]),
    ("Constitutional AI", ["CAI"]),
    ("Retrieval-Augmented Generation", ["RAG"]),
    ("Chain-of-Thought", ["CoT"]),
    ("Flash Attention", ["FlashAttention"]),
    ("LoRA", ["Low-Rank Adaptation"]),
    ("QLoRA", []),
    ("Quantization", ["GPTQ", "AWQ"]),
    ("Speculative Decoding", []),
    ("KV Cache Optimization", ["KV Cache"]),
    ("Multimodal Fusion", []),
    ("Sparse Attention", []),
    ("Rotary Position Embedding", ["RoPE"]),
    ("Group Query Attention", ["GQA"]),
    ("Sliding Window Attention", ["SWA"]),
    ("Tree of Thought", ["ToT"]),
    ("Tool Use", ["Function Calling"]),
    ("GGUF", ["GGML"]),
    ("Tokenizer BPE", ["Byte Pair Encoding"]),
    ("Distillation", ["Knowledge Distillation"]),
    ("Synthetic Data Generation", []),
    ("Red Teaming", []),
]

TOPICS = [
    ("AI Safety", ["AI Alignment"]),
    ("AI Regulation", ["AI Governance"]),
    ("Open Source AI", ["Open-Source LLM"]),
    ("AI Agents", ["Autonomous Agents"]),
    ("Multimodal AI", []),
    ("AI in Healthcare", ["Medical AI"]),
    ("AI in Education", ["EdTech AI"]),
    ("AI Ethics", []),
    ("Explainable AI", ["XAI"]),
    ("AI Chip Design", ["AI Hardware"]),
    ("AI Copyright", ["AI and IP"]),
    ("AI Job Displacement", ["AI and Employment"]),
    ("Frontier Model Safety", []),
    ("AI Watermarking", []),
    ("Synthetic Media", ["Deepfakes"]),
    ("AI in Finance", ["FinTech AI"]),
    ("Responsible AI", []),
    ("AI Energy Consumption", ["AI and Climate"]),
    ("Model Collapse", []),
    ("Prompt Engineering", []),
]

PAPERS = [
    ("Attention Is All You Need v2", []),
    ("Scaling Laws for Neural Language Models (2025)", []),
    ("Constitutional AI: Harmlessness from AI Feedback", []),
    ("Direct Preference Optimization", []),
    ("Toolformer: Language Models Can Teach Themselves to Use Tools", []),
    ("Chain-of-Thought Prompting Elicits Reasoning", []),
    ("Flash Attention: Fast and Memory-Efficient Attention", []),
    ("LoRA: Low-Rank Adaptation of Large Language Models", []),
    ("LLM Agents: A Survey", []),
    ("Retrieval-Augmented Generation for Knowledge-Intensive NLP", []),
    ("Tree of Thoughts: Deliberate Problem Solving with LLMs", []),
    ("Self-Play Fine-Tuning for Language Models", []),
    ("Mixture of Experts Meets Instruction Tuning", []),
    ("Scaling Data-Constrained Language Models", []),
    ("Textbooks Are All You Need", []),
]

REPOS = [
    ("transformers", ["huggingface/transformers"]),
    ("llama.cpp", []),
    ("vllm", ["vllm-project/vllm"]),
    ("langchain", ["langchain-ai/langchain"]),
    ("ollama", ["ollama/ollama"]),
    ("open-interpreter", []),
    ("AutoGPT", ["Significant-Gravitas/AutoGPT"]),
    ("gpt4all", []),
    ("text-generation-webui", ["oobabooga"]),
    ("LocalAI", []),
]

PROGRAMS = [
    ("EU AI Act", ["AI Act"]),
    ("NIST AI RMF", ["AI Risk Management Framework"]),
    ("Executive Order on AI Safety", ["Biden AI EO"]),
    ("Frontier Model Forum", []),
    ("Partnership on AI", ["PAI"]),
    ("AI Safety Institute", ["AISI"]),
    ("DARPA AI Programs", []),
    ("NSF AI Research Institutes", []),
]

EVENTS = [
    ("NeurIPS 2025", []),
    ("ICML 2026", []),
    ("AAAI 2026", []),
    ("AI Safety Summit 2026", []),
    ("GTC 2026", ["GPU Technology Conference 2026"]),
]

LOCATIONS = [
    ("San Francisco", ["SF"]),
    ("London", []),
    ("Paris", []),
    ("Beijing", []),
    ("Washington DC", ["DC"]),
]

# Pool by type
ENTITY_POOLS = {
    "Org": ORGS,
    "Person": PEOPLE,
    "Model": MODELS,
    "Tool": TOOLS,
    "Dataset": DATASETS,
    "Benchmark": BENCHMARKS,
    "Tech": TECH,
    "Topic": TOPICS,
    "Paper": PAPERS,
    "Repo": REPOS,
    "Program": PROGRAMS,
    "Event": EVENTS,
    "Location": LOCATIONS,
}

# Type distribution weights (how many of each type per 100 entities)
TYPE_WEIGHTS = {
    "Org": 15,
    "Person": 12,
    "Model": 18,
    "Tool": 10,
    "Dataset": 6,
    "Benchmark": 6,
    "Tech": 14,
    "Topic": 8,
    "Paper": 5,
    "Repo": 3,
    "Program": 2,
    "Event": 1,
    "Location": 0,  # only in large/stress
}

# Relation rules: (source_type, target_type, relation, kind_weights, conf_range)
# kind_weights: {"asserted": w, "inferred": w, "hypothesis": w}
RELATION_RULES = [
    ("Org", "Model", "CREATED", {"asserted": 8, "inferred": 2}, (0.85, 0.99)),
    ("Org", "Model", "LAUNCHED", {"asserted": 9, "inferred": 1}, (0.88, 0.99)),
    ("Org", "Tool", "CREATED", {"asserted": 7, "inferred": 3}, (0.80, 0.98)),
    ("Org", "Paper", "PUBLISHED", {"asserted": 9, "inferred": 1}, (0.90, 0.99)),
    ("Org", "Org", "PARTNERED_WITH", {"asserted": 5, "inferred": 3, "hypothesis": 2}, (0.55, 0.90)),
    ("Org", "Org", "ACQUIRED", {"asserted": 8, "inferred": 2}, (0.80, 0.99)),
    ("Org", "Org", "FUNDED", {"asserted": 7, "inferred": 3}, (0.70, 0.95)),
    ("Org", "Person", "HIRED", {"asserted": 8, "inferred": 2}, (0.75, 0.98)),
    ("Org", "Topic", "MENTIONS", {"asserted": 9, "inferred": 1}, (0.70, 0.95)),
    ("Org", "Program", "COMPLIES_WITH", {"asserted": 4, "inferred": 4, "hypothesis": 2}, (0.50, 0.85)),
    ("Person", "Org", "OPERATES", {"asserted": 9, "inferred": 1}, (0.90, 0.99)),
    ("Person", "Model", "CREATED", {"asserted": 6, "inferred": 4}, (0.70, 0.95)),
    ("Person", "Paper", "PUBLISHED", {"asserted": 9, "inferred": 1}, (0.90, 0.99)),
    ("Model", "Tech", "USES_TECH", {"inferred": 6, "asserted": 3, "hypothesis": 1}, (0.55, 0.92)),
    ("Model", "Dataset", "TRAINED_ON", {"asserted": 4, "inferred": 3, "hypothesis": 3}, (0.45, 0.90)),
    ("Model", "Benchmark", "EVALUATED_ON", {"asserted": 8, "inferred": 2}, (0.80, 0.98)),
    ("Model", "Model", "DEPENDS_ON", {"inferred": 5, "hypothesis": 5}, (0.40, 0.75)),
    ("Tool", "Model", "INTEGRATES_WITH", {"asserted": 7, "inferred": 3}, (0.75, 0.95)),
    ("Tool", "Tech", "USES_TECH", {"asserted": 4, "inferred": 5, "hypothesis": 1}, (0.60, 0.90)),
    ("Tool", "Tool", "INTEGRATES_WITH", {"asserted": 5, "inferred": 4, "hypothesis": 1}, (0.55, 0.88)),
    ("Dataset", "Tech", "USES_TECH", {"inferred": 7, "hypothesis": 3}, (0.40, 0.80)),
    ("Paper", "Tech", "USES_TECH", {"asserted": 7, "inferred": 3}, (0.75, 0.95)),
    ("Paper", "Model", "EVALUATED_ON", {"asserted": 6, "inferred": 4}, (0.70, 0.92)),
    ("Benchmark", "Model", "MEASURES", {"asserted": 8, "inferred": 2}, (0.80, 0.98)),
    ("Program", "Org", "GOVERNS", {"asserted": 6, "inferred": 3, "hypothesis": 1}, (0.55, 0.90)),
    ("Program", "Topic", "MENTIONS", {"asserted": 8, "inferred": 2}, (0.70, 0.95)),
    ("Repo", "Model", "INTEGRATES_WITH", {"asserted": 7, "inferred": 3}, (0.70, 0.92)),
    ("Repo", "Tech", "USES_TECH", {"asserted": 6, "inferred": 4}, (0.65, 0.90)),
]

# Dependency-only relations (for dependencies view)
DEP_RELATIONS = {
    "USES_TECH", "USES_MODEL", "USES_DATASET", "TRAINED_ON",
    "EVALUATED_ON", "INTEGRATES_WITH", "DEPENDS_ON", "REQUIRES",
    "PRODUCES", "MEASURES",
}

# Sources for realistic URLs and doc generation
SOURCES = [
    ("OpenAI Blog", "openai.com/blog"),
    ("Anthropic Blog", "anthropic.com/news"),
    ("Google AI Blog", "blog.google/technology/ai"),
    ("Meta AI Blog", "ai.meta.com/blog"),
    ("Hugging Face Blog", "huggingface.co/blog"),
    ("arXiv", "arxiv.org/abs"),
    ("TechCrunch", "techcrunch.com"),
    ("The Verge", "theverge.com"),
    ("VentureBeat", "venturebeat.com"),
    ("MIT Technology Review", "technologyreview.com"),
    ("Wired", "wired.com"),
    ("Ars Technica", "arstechnica.com"),
    ("LangChain Blog", "blog.langchain.dev"),
    ("Microsoft Research Blog", "microsoft.com/en-us/research/blog"),
    ("Nvidia Blog", "blogs.nvidia.com"),
    ("The Gradient", "thegradient.pub"),
    ("Weights & Biases Blog", "wandb.ai/articles"),
    ("Nextgov", "nextgov.com"),
    ("Reuters", "reuters.com/technology"),
    ("Bloomberg", "bloomberg.com/technology"),
]

# Snippet templates for evidence
SNIPPET_TEMPLATES = {
    "CREATED": [
        "{source} announced {target}, its latest {category}...",
        "{source} unveiled {target} at its annual developer conference...",
        "The team at {source} released {target} after months of development...",
    ],
    "LAUNCHED": [
        "{source} launched {target} to general availability today...",
        "{source} made {target} publicly accessible for the first time...",
        "After a limited beta, {source} opened {target} to all users...",
    ],
    "USES_TECH": [
        "{source} leverages {target} to achieve state-of-the-art performance...",
        "Under the hood, {source} implements {target} for improved efficiency...",
        "Technical details reveal {source} relies heavily on {target}...",
    ],
    "TRAINED_ON": [
        "{source} was trained on {target} comprising billions of tokens...",
        "The training corpus for {source} includes {target}...",
        "{source} utilized {target} as part of its pre-training data mix...",
    ],
    "EVALUATED_ON": [
        "{source} achieves {score}% on {target}, setting a new record...",
        "On the {target} benchmark, {source} scored {score}%...",
        "Evaluation results show {source} reaching {score}% on {target}...",
    ],
    "INTEGRATES_WITH": [
        "{source} now supports {target} with full feature parity...",
        "The latest release of {source} adds native {target} integration...",
        "{source} announced official support for {target}...",
    ],
    "PARTNERED_WITH": [
        "{source} and {target} announced a strategic partnership...",
        "A new collaboration between {source} and {target} aims to...",
        "{source} partnered with {target} to accelerate AI development...",
    ],
    "FUNDED": [
        "{source} invested ${amount}M in {target}...",
        "{target} received funding from {source} in its latest round...",
        "{source} led a ${amount}M investment round for {target}...",
    ],
    "ACQUIRED": [
        "{source} completed its acquisition of {target}...",
        "{target} was acquired by {source} for an undisclosed sum...",
        "{source} announced the acquisition of {target}...",
    ],
    "PUBLISHED": [
        "{source} published \"{target}\" detailing novel approaches...",
        "Researchers at {source} released the paper \"{target}\"...",
        "{source} released \"{target}\" on arXiv...",
    ],
    "OPERATES": [
        "{source} serves as CEO of {target}...",
        "{source} leads {target} as its chief executive...",
        "{source} has been at the helm of {target} since...",
    ],
    "HIRED": [
        "{source} hired {target} to lead its AI research division...",
        "{target} joined {source} in a senior technical role...",
        "{source} brought on {target} from a competing lab...",
    ],
    "MENTIONS": [
        "The article discusses {target} in the context of recent developments...",
        "{target} was mentioned as a key factor in the analysis...",
        "Multiple references to {target} appear throughout the report...",
    ],
    "DEPENDS_ON": [
        "{source} builds on top of {target} architecture...",
        "Core components of {source} are derived from {target}...",
        "{source} requires {target} as a foundation...",
    ],
    "MEASURES": [
        "{source} provides standardized evaluation of {target}...",
        "The {source} benchmark measures {target} across multiple tasks...",
        "{source} has become the standard for evaluating {target}...",
    ],
    "GOVERNS": [
        "{source} establishes compliance requirements for {target}...",
        "Under {source}, {target} must adhere to new standards...",
        "{source} regulation now covers {target} operations...",
    ],
    "COMPLIES_WITH": [
        "{source} announced compliance with {target} requirements...",
        "{source} updated its policies to align with {target}...",
        "{source} achieved certification under {target}...",
    ],
}

# Default fallback snippet
DEFAULT_SNIPPETS = [
    "{source} is connected to {target} through recent developments...",
    "Analysis reveals a relationship between {source} and {target}...",
    "Reports indicate {source} and {target} are closely linked...",
]


def slugify(name):
    """Convert a name to a slug for canonical IDs."""
    return (
        name.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
        .replace("'", "")
        .replace("&", "and")
        .replace("+", "_plus")
        .replace("/", "_")
    )[:40]


def type_prefix(entity_type):
    """Get the ID prefix for an entity type."""
    return {
        "Org": "org",
        "Person": "person",
        "Model": "model",
        "Tool": "tool",
        "Dataset": "dataset",
        "Benchmark": "benchmark",
        "Tech": "tech",
        "Topic": "topic",
        "Paper": "paper",
        "Repo": "repo",
        "Program": "program",
        "Event": "event",
        "Location": "location",
    }[entity_type]


def random_date(rng, start=DATE_START, end=DATE_END):
    """Random date in range."""
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, delta))


def format_date(dt):
    return dt.strftime("%Y-%m-%d")


def make_evidence(rng, rel, source_label, target_label, source_type, doc_date):
    """Generate a realistic evidence object."""
    source_info = rng.choice(SOURCES)
    source_name, domain = source_info
    doc_slug = slugify(f"{source_label}_{target_label}")[:30]
    doc_date_str = format_date(doc_date)
    doc_id = f"{doc_date_str}_{slugify(source_name)[:15]}_{rng.randint(1000, 9999)}"

    templates = SNIPPET_TEMPLATES.get(rel, DEFAULT_SNIPPETS)
    template = rng.choice(templates)
    snippet = template.format(
        source=source_label,
        target=target_label,
        category=source_type.lower(),
        score=rng.randint(70, 99),
        amount=rng.choice([50, 100, 150, 200, 300, 500, 1000, 2000]),
    )
    # Truncate to ~200 chars
    if len(snippet) > 200:
        snippet = snippet[:197] + "..."

    return {
        "docId": doc_id,
        "url": f"https://{domain}/{doc_date_str.replace('-', '/')}/{doc_slug}",
        "published": doc_date_str,
        "snippet": snippet,
    }


def make_document_node(evidence, rng):
    """Create a Document node from an evidence object."""
    titles = [
        f"Analysis: {rng.choice(['New Developments', 'Emerging Trends', 'Key Updates', 'Breaking News'])} in AI",
        f"Report: {rng.choice(['Industry', 'Research', 'Technical', 'Market'])} {rng.choice(['Overview', 'Update', 'Analysis', 'Summary'])}",
        f"{rng.choice(['How', 'Why', 'What'])} {rng.choice(['AI Labs', 'Researchers', 'Companies', 'Engineers'])} {rng.choice(['Are Building', 'Are Rethinking', 'Approach', 'View'])} {rng.choice(['the Future', 'New Models', 'Scale', 'Safety'])}",
    ]

    source_name = evidence["url"].split("/")[2].replace("www.", "")
    # Derive a readable source name
    for name, domain in SOURCES:
        if domain in evidence["url"]:
            source_name = name
            break

    return {
        "data": {
            "id": f"doc:{evidence['docId']}",
            "label": rng.choice(titles),
            "type": "Document",
            "url": evidence["url"],
            "source": source_name,
            "publishedAt": evidence["published"],
        }
    }


class GraphGenerator:
    """Generate a realistic knowledge graph at a given scale."""

    def __init__(self, target_nodes, target_edges, seed=SEED):
        self.rng = random.Random(seed)
        self.target_nodes = target_nodes
        self.target_edges = target_edges
        self.entities = []  # list of {id, label, type, aliases, ...}
        self.edges = []
        self.entity_ids = set()
        self.edge_keys = set()  # (source_id, target_id, rel) dedup

    def _pick_entities(self):
        """Select entities from pools matching type distribution."""
        # Adjust weights for scale
        weights = dict(TYPE_WEIGHTS)
        if self.target_nodes >= 500:
            weights["Location"] = 2
            weights["Event"] = 2
            weights["Program"] = 3

        total_weight = sum(weights.values())
        counts = {}
        remaining = self.target_nodes
        for etype, w in weights.items():
            counts[etype] = max(1, int(self.target_nodes * w / total_weight))
            remaining -= counts[etype]

        # Distribute remainder to high-weight types
        for etype in sorted(weights, key=weights.get, reverse=True):
            if remaining <= 0:
                break
            counts[etype] += 1
            remaining -= 1

        for etype, count in counts.items():
            pool = ENTITY_POOLS.get(etype, [])
            if not pool:
                continue
            # Take up to count from pool, cycling if needed
            selected = []
            for i in range(min(count, len(pool))):
                selected.append(pool[i])
            # If we need more than the pool has, generate synthetic variants
            for i in range(len(pool), count):
                base = pool[i % len(pool)]
                variant_name = f"{base[0]} {self.rng.choice(['v2', 'Pro', 'Plus', 'Next', 'Ultra', 'Lite', 'Mini', 'Max', 'Edge', 'Core'])}"
                selected.append((variant_name, []))

            for name, aliases in selected:
                eid = f"{type_prefix(etype)}:{slugify(name)}"
                if eid in self.entity_ids:
                    continue
                self.entity_ids.add(eid)

                first_seen = random_date(self.rng)
                last_seen = random_date(
                    self.rng,
                    start=first_seen,
                    end=DATE_END,
                )
                days_active = (last_seen - first_seen).days + 1

                # Generate realistic mention counts based on type importance
                base_mentions = self.rng.randint(2, 50)
                if etype in ("Model", "Org"):
                    base_mentions = self.rng.randint(10, 120)
                elif etype in ("Tech", "Topic"):
                    base_mentions = self.rng.randint(5, 80)
                elif etype in ("Person",):
                    base_mentions = self.rng.randint(3, 60)

                mention_7d = max(0, int(base_mentions * self.rng.uniform(0.1, 0.5)))
                mention_30d = max(mention_7d, int(base_mentions * self.rng.uniform(0.5, 1.2)))

                velocity = round(self.rng.uniform(0.05, 0.98), 2)
                # Boost velocity for recent entities
                if (DATE_END - last_seen).days < 7:
                    velocity = min(1.0, velocity + self.rng.uniform(0.1, 0.3))
                velocity = round(velocity, 2)

                self.entities.append({
                    "id": eid,
                    "label": name,
                    "type": etype,
                    "aliases": aliases,
                    "firstSeen": format_date(first_seen),
                    "lastSeen": format_date(last_seen),
                    "mentionCount7d": mention_7d,
                    "mentionCount30d": mention_30d,
                    "velocity": velocity,
                    "_firstSeenDt": first_seen,
                    "_lastSeenDt": last_seen,
                })

    def _build_type_index(self):
        """Index entities by type for efficient relation generation."""
        self.by_type = {}
        for e in self.entities:
            self.by_type.setdefault(e["type"], []).append(e)

    def _add_edge(self, source, target, rel, kind, confidence, evidence=None):
        """Add an edge, deduplicating by (source, target, rel)."""
        key = (source["id"], target["id"], rel)
        if key in self.edge_keys:
            return False
        if source["id"] == target["id"]:
            return False
        self.edge_keys.add(key)

        edge_data = {
            "id": f"e:{slugify(source['label'])}_{slugify(target['label'])}_{rel.lower()}",
            "source": source["id"],
            "target": target["id"],
            "rel": rel,
            "kind": kind,
            "confidence": round(confidence, 2),
        }
        if evidence:
            edge_data["evidence"] = evidence

        self.edges.append({"data": edge_data})
        return True

    def _pick_kind(self, kind_weights):
        """Weighted random choice of edge kind."""
        kinds = list(kind_weights.keys())
        weights = [kind_weights[k] for k in kinds]
        return self.rng.choices(kinds, weights=weights, k=1)[0]

    def _generate_edges(self):
        """Generate edges following relation rules to hit target count."""
        attempts = 0
        max_attempts = self.target_edges * 10

        # First pass: ensure hub nodes get many edges
        hubs = sorted(self.entities, key=lambda e: e["mentionCount30d"], reverse=True)
        hub_set = set(h["id"] for h in hubs[: max(5, len(hubs) // 10)])

        while len(self.edges) < self.target_edges and attempts < max_attempts:
            attempts += 1
            rule = self.rng.choice(RELATION_RULES)
            src_type, tgt_type, rel, kind_weights, conf_range = rule

            sources = self.by_type.get(src_type, [])
            targets = self.by_type.get(tgt_type, [])
            if not sources or not targets:
                continue

            # Bias toward hub nodes 40% of the time
            if self.rng.random() < 0.4 and any(s["id"] in hub_set for s in sources):
                source = self.rng.choice(
                    [s for s in sources if s["id"] in hub_set] or sources
                )
            else:
                source = self.rng.choice(sources)

            target = self.rng.choice(targets)
            if source["id"] == target["id"]:
                continue

            kind = self._pick_kind(kind_weights)
            confidence = round(
                self.rng.uniform(conf_range[0], conf_range[1]), 2
            )

            # Generate evidence for asserted edges
            evidence = None
            if kind == "asserted":
                doc_date = random_date(
                    self.rng,
                    start=max(source["_firstSeenDt"], target["_firstSeenDt"]),
                    end=DATE_END,
                )
                num_evidence = self.rng.choices([1, 2, 3, 4], weights=[50, 30, 15, 5])[0]
                evidence = []
                for _ in range(num_evidence):
                    ev = make_evidence(
                        self.rng, rel, source["label"], target["label"],
                        source["type"], doc_date,
                    )
                    evidence.append(ev)
                    doc_date = random_date(self.rng, start=doc_date, end=DATE_END)

            self._add_edge(source, target, rel, kind, confidence, evidence)

    def generate(self):
        """Run the full generation pipeline."""
        self._pick_entities()
        self._build_type_index()
        self._generate_edges()

    def _entity_node(self, entity, include_metrics=True):
        """Convert internal entity to Cytoscape node."""
        data = {
            "id": entity["id"],
            "label": entity["label"],
            "type": entity["type"],
            "aliases": entity["aliases"],
            "firstSeen": entity["firstSeen"],
            "lastSeen": entity["lastSeen"],
        }
        if include_metrics:
            data["mentionCount7d"] = entity["mentionCount7d"]
            data["mentionCount30d"] = entity["mentionCount30d"]
            data["velocity"] = entity["velocity"]
        return {"data": data}

    def _doc_node(self, entity):
        """Convert Document-type entity to a doc node (for mentions view)."""
        return {
            "data": {
                "id": entity["id"],
                "label": entity["label"],
                "type": "Document",
                "url": entity.get("url", ""),
                "source": entity.get("source", ""),
                "publishedAt": entity["firstSeen"],
            }
        }

    def export_trending(self):
        """Export trending view: high-velocity/novelty nodes + their edges."""
        # Pick top nodes by velocity
        threshold = max(10, self.target_nodes // 4)
        sorted_entities = sorted(
            self.entities, key=lambda e: e["velocity"], reverse=True
        )
        trending = sorted_entities[:threshold]
        trending_ids = set(e["id"] for e in trending)

        nodes = [self._entity_node(e) for e in trending]
        edges = [
            edge for edge in self.edges
            if edge["data"]["source"] in trending_ids
            and edge["data"]["target"] in trending_ids
        ]

        return self._wrap("trending", nodes, edges, filters={
            "minVelocity": 0.1,
            "minConfidence": 0.3,
        })

    def export_claims(self):
        """Export claims view: all semantic entity-to-entity relations."""
        # Exclude MENTIONS — those go to mentions view
        claim_edges = [
            e for e in self.edges if e["data"]["rel"] != "MENTIONS"
        ]
        # Gather referenced entity IDs
        claim_ids = set()
        for e in claim_edges:
            claim_ids.add(e["data"]["source"])
            claim_ids.add(e["data"]["target"])

        entity_map = {e["id"]: e for e in self.entities}
        nodes = [
            self._entity_node(entity_map[eid])
            for eid in claim_ids
            if eid in entity_map
        ]

        return self._wrap("claims", nodes, claim_edges)

    def export_mentions(self):
        """Export mentions view: Document <-> Entity MENTIONS edges."""
        # Create document nodes from evidence across all edges
        doc_nodes = {}
        mention_edges = []
        entity_ids_in_mentions = set()

        for edge in self.edges:
            evidence_list = edge["data"].get("evidence", [])
            for ev in evidence_list:
                doc_id = f"doc:{ev['docId']}"
                if doc_id not in doc_nodes:
                    doc_nodes[doc_id] = make_document_node(ev, self.rng)
                    doc_nodes[doc_id]["data"]["id"] = doc_id

                # Create MENTIONS edges from doc to source and target entities
                for entity_id in [edge["data"]["source"], edge["data"]["target"]]:
                    mention_key = (doc_id, entity_id)
                    edge_id = f"e:{doc_id}->{entity_id}"
                    if edge_id not in {me["data"]["id"] for me in mention_edges}:
                        mention_edges.append({
                            "data": {
                                "id": edge_id,
                                "source": doc_id,
                                "target": entity_id,
                                "rel": "MENTIONS",
                                "kind": "asserted",
                                "confidence": round(self.rng.uniform(0.80, 1.0), 2),
                            }
                        })
                        entity_ids_in_mentions.add(entity_id)

        # Limit for sanity at large scale
        max_docs = min(len(doc_nodes), self.target_nodes // 2)
        doc_list = list(doc_nodes.values())[:max_docs]
        doc_id_set = set(d["data"]["id"] for d in doc_list)

        # Filter edges to only those referencing kept docs
        mention_edges = [
            e for e in mention_edges
            if e["data"]["source"] in doc_id_set
        ]

        # Gather entity IDs referenced by kept edges
        entity_ids_in_mentions = set()
        for e in mention_edges:
            entity_ids_in_mentions.add(e["data"]["target"])

        entity_map = {e["id"]: e for e in self.entities}
        entity_nodes = [
            self._entity_node(entity_map[eid], include_metrics=False)
            for eid in entity_ids_in_mentions
            if eid in entity_map
        ]

        nodes = doc_list + entity_nodes
        return self._wrap("mentions", nodes, mention_edges)

    def export_dependencies(self):
        """Export dependencies view: only dependency-type relations."""
        dep_edges = [
            e for e in self.edges if e["data"]["rel"] in DEP_RELATIONS
        ]
        dep_ids = set()
        for e in dep_edges:
            dep_ids.add(e["data"]["source"])
            dep_ids.add(e["data"]["target"])

        entity_map = {e["id"]: e for e in self.entities}
        nodes = [
            self._entity_node(entity_map[eid])
            for eid in dep_ids
            if eid in entity_map
        ]

        return self._wrap("dependencies", nodes, dep_edges)

    def _wrap(self, view, nodes, edges, filters=None):
        """Wrap nodes/edges in the standard export format."""
        meta = {
            "view": view,
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "exportedAt": "2026-01-25T12:00:00Z",
            "dateRange": {
                "start": format_date(DATE_START),
                "end": format_date(DATE_END),
            },
        }
        if filters:
            meta["filters"] = filters

        return {
            "meta": meta,
            "elements": {
                "nodes": nodes,
                "edges": edges,
            },
        }


# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

TIERS = {
    "small": {"nodes": 15, "edges": 15, "seed": 42},
    "medium": {"nodes": 150, "edges": 400, "seed": 123},
    "large": {"nodes": 500, "edges": 1500, "seed": 456},
    "stress": {"nodes": 2000, "edges": 5000, "seed": 789},
}


def generate_tier(tier_name, config):
    """Generate all 4 views for a tier and write to disk."""
    out_dir = os.path.join(OUTPUT_BASE, tier_name)
    os.makedirs(out_dir, exist_ok=True)

    gen = GraphGenerator(
        target_nodes=config["nodes"],
        target_edges=config["edges"],
        seed=config["seed"],
    )
    gen.generate()

    views = {
        "trending.json": gen.export_trending(),
        "claims.json": gen.export_claims(),
        "mentions.json": gen.export_mentions(),
        "dependencies.json": gen.export_dependencies(),
    }

    for filename, data in views.items():
        path = os.path.join(out_dir, filename)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        nc = data["meta"]["nodeCount"]
        ec = data["meta"]["edgeCount"]
        print(f"  {filename:25s} {nc:5d} nodes  {ec:5d} edges")

    return views


def main():
    requested = sys.argv[1:] if len(sys.argv) > 1 else list(TIERS.keys())

    for tier_name in requested:
        if tier_name not in TIERS:
            print(f"Unknown tier: {tier_name}. Available: {', '.join(TIERS)}")
            continue

        config = TIERS[tier_name]
        print(f"\n=== {tier_name.upper()} tier ({config['nodes']} nodes, {config['edges']} edges target) ===")
        generate_tier(tier_name, config)

    print("\nDone. Files written to web/data/graphs/{tier}/")


if __name__ == "__main__":
    main()
