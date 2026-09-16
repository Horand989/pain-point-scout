"""
Facebook group profiles — for generating a DISTINCT, tailored post per community.

We never scrape or post to Facebook (against ToS, ban risk, and excluded by spec).
This only produces post *drafts* that Horace edits and posts BY HAND, rotating a
few groups per day so nothing reads as spam or cross-posting.

Edit this list freely: add/remove groups, adjust the audience/angle/tone/region.
"""

# How many groups to write posts for each day (rotates through the full list so
# you never post the same thing to all of them at once).
FB_GROUPS_PER_DAY = 4

FACEBOOK_GROUPS = [
    {"name": "Networking Business Owners & Entrepreneurs",
     "audience": "owners actively looking to connect and network",
     "region": "global", "angle": "making connections and mutual introductions",
     "tone": "warm, connective"},
    {"name": "Side Hustle Opportunities",
     "audience": "people building a side hustle while still employed",
     "region": "global", "angle": "starting small, first steps, side income",
     "tone": "encouraging, practical, low-pressure"},
    {"name": "Young Entrepreneurs",
     "audience": "younger, early-stage founders finding their feet",
     "region": "global", "angle": "starting out, learning fast, ambition",
     "tone": "energetic, peer-to-peer"},
    {"name": "Small Business Owner & Entrepreneur",
     "audience": "established small business owners",
     "region": "global", "angle": "running and growing a small business",
     "tone": "practical, peer"},
    {"name": "Canadian Business Owner & Entrepreneur",
     "audience": "Canadian business owners",
     "region": "Canada", "angle": "Canadian business realities (GST/HST, local market)",
     "tone": "practical, local, down-to-earth"},
    {"name": "Business Owner & Entrepreneurs",
     "audience": "general mix of owners and entrepreneurs",
     "region": "global", "angle": "day-to-day of running a business",
     "tone": "practical"},
    {"name": "Small Business Owner + Network Circle",
     "audience": "owners in a close networking circle",
     "region": "global", "angle": "networking and helping each other grow",
     "tone": "warm, community"},
    {"name": "Support Small Business",
     "audience": "small business owners and their supporters",
     "region": "global", "angle": "community support, lifting each other up",
     "tone": "supportive, community-first"},
    {"name": "Small Business Owners / Entrepreneurs / Marketing",
     "audience": "owners focused on marketing and getting customers",
     "region": "global", "angle": "marketing, visibility, winning customers",
     "tone": "practical, growth-minded"},
    {"name": "Business Owner in USA",
     "audience": "US-based business owners",
     "region": "USA", "angle": "US business realities",
     "tone": "practical, local"},
    {"name": "Small Business Networking USA",
     "audience": "US owners who want to network",
     "region": "USA", "angle": "networking within the US market",
     "tone": "connective, local"},
    {"name": "Black Business Owners",
     "audience": "Black entrepreneurs building and supporting one another",
     "region": "global", "angle": "building while wearing every hat, community and authenticity",
     "tone": "genuine, community-centered, respectful (never pandering)"},
]


def groups_for_today(day_index: int, per_day: int = FB_GROUPS_PER_DAY):
    """Rotate through the group list so a different subset comes up each day."""
    n = len(FACEBOOK_GROUPS)
    if n == 0:
        return []
    start = (day_index * per_day) % n
    picked = [FACEBOOK_GROUPS[(start + i) % n] for i in range(min(per_day, n))]
    return picked
