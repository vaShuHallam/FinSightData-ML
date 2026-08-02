"""
Sample NewsAPI-shaped responses, used when NEWSAPI_KEY is missing/invalid.

This mirrors the actual response shape from
https://newsapi.org/docs/endpoints/everything so swapping to live data later
requires no parsing changes — only real values.
"""

SAMPLE_NEWSAPI_RESPONSE = {
    "status": "ok",
    "totalResults": 5,
    "articles": [
        {
            "source": {"id": "reuters", "name": "Reuters"},
            "author": "Jane Doe",
            "title": "Apple beats quarterly earnings expectations on strong iPhone demand",
            "description": "Apple Inc reported quarterly revenue above analyst estimates...",
            "content": (
                "Apple Inc reported quarterly revenue above analyst estimates on "
                "Thursday, driven by stronger than expected iPhone sales in China "
                "and continued growth in its services division. Shares rose in "
                "after-hours trading following the announcement."
            ),
            "url": "https://example.com/apple-earnings-beat",
            "publishedAt": "2026-07-01T14:32:00Z",
        },
        {
            "source": {"id": "bloomberg", "name": "Bloomberg"},
            "author": "John Smith",
            "title": "Tesla shares slide after production miss and price cut announcement",
            "description": "Tesla fell short of delivery targets in the latest quarter...",
            "content": (
                "Tesla fell short of delivery targets in the latest quarter and "
                "announced a fresh round of price cuts, raising concerns among "
                "analysts about shrinking margins amid growing competition from "
                "Chinese EV makers."
            ),
            "url": "https://example.com/tesla-shares-slide",
            "publishedAt": "2026-07-01T09:15:00Z",
        },
        {
            "source": {"id": "cnbc", "name": "CNBC"},
            "author": "Alex Chen",
            "title": "Microsoft unveils new AI features across Office suite, stock hits record high",
            "description": "Microsoft announced a major expansion of its Copilot AI features...",
            "content": (
                "Microsoft announced a major expansion of its Copilot AI features "
                "across its Office product suite on Wednesday, sending shares to a "
                "record high as investors cheered the company's aggressive push "
                "into generative AI tools for enterprise customers."
            ),
            "url": "https://example.com/microsoft-ai-record-high",
            "publishedAt": "2026-06-30T18:45:00Z",
        },
        {
            "source": {"id": "reuters", "name": "Reuters"},
            "author": "Jane Doe",
            "title": "NVIDIA faces new export restrictions on advanced AI chips to China",
            "description": "The US government announced new restrictions on chip exports...",
            "content": (
                "The US government announced new restrictions on the export of "
                "advanced AI chips to China on Tuesday, a move that analysts warn "
                "could cut billions from NVIDIA's revenue in the region and "
                "escalate ongoing trade tensions between the two countries."
            ),
            "url": "https://example.com/nvidia-export-restrictions",
            "publishedAt": "2026-06-30T11:20:00Z",
        },
        {
            "source": {"id": "ft", "name": "Financial Times"},
            "author": "Maria Garcia",
            "title": "Amazon announces $10 billion investment in logistics automation",
            "description": "Amazon plans to expand its warehouse robotics program...",
            "content": (
                "Amazon plans to expand its warehouse robotics program with a $10 "
                "billion investment over the next three years, aiming to cut "
                "delivery times and reduce labor costs across its fulfillment "
                "network, the company said on Monday."
            ),
            "url": "https://example.com/amazon-logistics-investment",
            "publishedAt": "2026-06-29T16:00:00Z",
        },
    ],
}
