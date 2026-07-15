# Google Ads MCP — Complete Server

A comprehensive [Model Context Protocol](https://modelcontextprotocol.io) server exposing the full Google Ads API surface to AI assistants (Claude, Cursor, etc.) through 129 typed tools.

This is a **fork** of [`grantweston/google-ads-mcp-complete`](https://github.com/grantweston/google-ads-mcp-complete) maintained at [`smartiesmb/google-ads-mcp-complete`](https://github.com/smartiesmb/google-ads-mcp-complete) with significant additions: modern Google Ads API compatibility, conversion-goals management, keyword planner integration, asset link removal, geographic / age targeting management, and many production-grade fixes.

> **API version**: the client pins no explicit version, so it runs on whatever `google-ads` defaults to — **v24** with the currently pinned library (31.1.0). It follows the library forward on upgrade rather than being fixed at a version.

---

## What's New In This Fork

| Area | Additions |
|------|-----------|
| **API version** | Migrated off v21 to the modern API surface (Asset API for extensions, modern resource patterns); now tracks the `google-ads` library default (**v24** today) |
| **Conversions** | Full conversion-action lifecycle + customer/campaign **conversion-goals** management |
| **Keyword Planner** | `generate_keyword_ideas`, `generate_keyword_historical_metrics` |
| **Negative keywords** | Now includes campaign-level negatives in `list_keywords`; smart match-type parsing from `"phrase"` and `[exact]` wrapping |
| **Asset removal** | `remove_customer_asset`, `remove_campaign_asset`, `remove_ad_group_asset`, `remove_asset_group_asset` |
| **Targeting management** | `manage_age_targeting`, `manage_geo_targeting`, `optimize_geographic_targeting` |
| **Tracking URLs** | `tracking_url_template`, `final_url_suffix`, `url_custom_parameters` exposed on campaigns and ad groups |
| **Auth** | MCC `login_customer_id` is now always sent when accessing client accounts |
| **Server** | Typed `Resource` objects (uri / name / description / mimeType) with per-customer entries |

---

## Tool Catalog (129 tools)

### Account & Hierarchy
`list_accounts` · `get_account_info` · `get_account_hierarchy`

### Campaign Management
`create_campaign` · `update_campaign` · `pause_campaign` · `resume_campaign` · `delete_campaign` · `list_campaigns` · `get_campaign` · `get_campaign_overview` · `get_campaign_performance` · `copy_campaign` · `create_ad_schedule`

### Ad Group Management
`create_ad_group` · `update_ad_group` · `list_ad_groups` · `get_ad_group_performance` · `get_ad_group_performance_ranking`

### Ad Management
`create_responsive_search_ad` · `create_expanded_text_ad` · `list_ads` · `update_ad` · `pause_ad` · `enable_ad` · `delete_ad` · `compare_ad_performance` · `analyze_ad_strength_trends` · `calculate_roas_by_ad`

### Keyword Management
`add_keywords` (with quote/bracket match-type parsing) · `list_keywords` (incl. campaign-level negatives) · `update_keyword_bid` · `pause_keyword` · `enable_keyword` · `delete_keyword` · `add_negative_keywords` · `remove_negative_keyword` · `auto_suggest_negative_keywords` · `get_keyword_performance`

### Keyword Planner
`generate_keyword_ideas` · `generate_keyword_historical_metrics`

### Budgets
`create_budget` · `update_budget` · `list_budgets`

### Bidding
`create_portfolio_bidding_strategy` · `list_bidding_strategies` · `remove_bidding_strategy` · `set_bid_adjustments` · `get_bid_adjustment_performance`

### Extensions (Asset API, v23+)
`create_sitelink_extensions` · `create_callout_extensions` · `create_structured_snippet_extensions` · `create_call_extensions` · `list_extensions` · `delete_extension`

### Assets
`upload_image_asset` · `upload_text_asset` · `list_assets` · `remove_customer_asset` · `remove_campaign_asset` · `remove_ad_group_asset` · `remove_asset_group_asset`

### Audiences
`list_audiences` · `create_custom_audience` · `add_audience_targeting` · `get_audience_performance`

### Conversions
`create_conversion_action` · `update_conversion_action` · `remove_conversion_action` · `get_conversion_action` · `list_conversion_actions` · `upload_click_conversion` · `upload_call_conversion`

### Conversion Goals (customer & campaign level)
`list_customer_conversion_goals` · `update_customer_conversion_goal` · `list_campaign_conversion_goals` · `update_campaign_conversion_goal`

### Targeting (Geo, Demographics, Devices)
`get_location_performance` · `manage_geo_targeting` · `optimize_geographic_targeting` · `manage_age_targeting` · `get_device_performance`

### Reporting & Insights
`get_search_terms_report` · `get_search_terms_insights` · `get_change_history` · `identify_optimization_opportunities` · `get_recommendations` · `apply_recommendation` · `run_gaql_query` (raw GAQL escape hatch)

---

## Installation

### Prerequisites
- Python 3.10+
- A Google Ads account with API access
- A developer token (Basic or Standard access)

### Clone & install

```bash
git clone https://github.com/smartiesmb/google-ads-mcp-complete.git
cd google-ads-mcp-complete

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -e .
```

### Get your credentials

1. **Developer token**: Google Ads → Tools & Settings → API Center → request a token (Basic Access is enough).
2. **OAuth 2.0 client**: [Google Cloud Console](https://console.cloud.google.com/) → enable Google Ads API → create an OAuth 2.0 Client ID (Desktop app type).
3. **Refresh token**: run any standard OAuth flow against the `https://www.googleapis.com/auth/adwords` scope and store the resulting refresh token.
4. **MCC `login_customer_id`** *(recommended)*: the 10-digit ID of your Manager account. The fork always sends this header when calling client accounts.

---

## Configuration

You can configure the server in either of two ways.

### Option 1 — `config.json` at repo root

```json
{
  "client_id": "YOUR_OAUTH_CLIENT_ID",
  "client_secret": "YOUR_OAUTH_CLIENT_SECRET",
  "refresh_token": "YOUR_REFRESH_TOKEN",
  "developer_token": "YOUR_DEVELOPER_TOKEN",
  "login_customer_id": "1234567890",
  "use_proto_plus": true
}
```

### Option 2 — Environment variables (recommended for MCP)

```
GOOGLE_ADS_DEVELOPER_TOKEN
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
GOOGLE_ADS_LOGIN_CUSTOMER_ID
```

---

## MCP Integration

### Claude Desktop / Claude Code

Add to `~/.claude/mcp.json` (macOS/Linux) or `%USERPROFILE%\.claude\mcp.json` (Windows):

```json
{
  "mcpServers": {
    "google-ads": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/google-ads-mcp-complete/run_server.py"],
      "env": {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "...",
        "GOOGLE_ADS_CLIENT_ID": "...",
        "GOOGLE_ADS_CLIENT_SECRET": "...",
        "GOOGLE_ADS_REFRESH_TOKEN": "...",
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID": "1234567890"
      }
    }
  }
}
```

Restart your client. The server should advertise 129 tools and a handful of `googleads://` resources (one per accessible customer).

### Resources exposed

- `googleads://accounts` — every account the auth token can access
- `googleads://customers/{id}` — per-customer summary
- `googleads://documentation` — usage cheatsheet
- `googleads://gaql-reference` — GAQL syntax reference
- `googleads://error-codes` — common API error codes

---

## Usage Examples (natural-language prompts)

> *"List all my Google Ads accounts and show me which ones are MCC managers."*

> *"Create a Search campaign in account 1234567890 named 'Brand FR-EST 2026Q2', daily budget €50, MAXIMIZE_CLICKS, target Switzerland (French + German), with a French RSA pointing to https://example.ch."*

> *"For campaign X, generate 30 keyword ideas around 'machine à café professionnelle', return historical metrics, and add the top 10 as exact-match keywords with a CPC max of €1.20."*

> *"Audit account Y: list all conversion actions, show which ones are tied to active customer-level conversion goals, and pause any conversion action that hasn't fired in 90 days."*

> *"On campaign Z, exclude users aged 18–24 and apply a +25% bid modifier to mobile devices."*

> *"Find the top 20 search terms with spend > €5 and zero conversions across all Search campaigns from the last 30 days, and add them as campaign-level negative keywords."*

---

## Architecture

```
src/
├── server.py              MCP server, resource handlers, tool dispatcher
├── auth.py                OAuth2 / refresh-token / MCC login_customer_id
├── error_handler.py       Retry policy, GoogleAdsException unwrapping
├── tools.py               Base tool class, account & basic ops
├── tools_complete.py      Central registry — wires every tool into MCP
├── tools_campaigns.py     Campaigns + scheduling + tracking URLs
├── tools_ad_groups.py     Ad groups + tracking URLs
├── tools_ads.py           RSA / ETA + performance analytics
├── tools_keywords.py      Keywords, negatives, Keyword Planner
├── tools_extensions.py    Asset API extensions (v23+)
├── tools_assets.py        Image/text assets + asset link removal
├── tools_audiences.py     Custom audiences, targeting, performance
├── tools_bidding.py       Portfolio strategies + bid adjustments
├── tools_budgets.py       Shared budgets
├── tools_conversions.py   Conversion actions + goals + uploads
├── tools_geography.py     Location targeting + geo optimization + age
├── tools_reporting.py     Search terms, change history, GAQL
└── utils.py               Currency, date, micros conversion
```

---

## Development

### Run locally

```bash
export LOG_LEVEL=DEBUG
python run_server.py
```

The server speaks MCP over stdio. To smoke-test outside an MCP client, you can import the registry directly:

```python
from src.tools_complete import GoogleAdsTools
from src.auth import GoogleAdsAuthManager
from src.error_handler import ErrorHandler

tools = GoogleAdsTools(GoogleAdsAuthManager(), ErrorHandler())
print(len(tools.get_all_tools()), "tools registered")
```

### Branching

- `main` — stable, tracks the original upstream
- `feat/conversion-goals-and-fixes` — current development branch with all fork additions

### Contributing back

PRs welcome. Please:
- keep changes API-version-aware (v23 fields, modern Asset API)
- add or update GAQL queries when the underlying field set changes
- avoid committing client-specific scripts (this fork's `.gitignore` excludes `audit_*.py`, `fix_*.py`, `diag_*.py`, etc.)

---

## Security

- **Never** commit `config.json`, `google-ads.yaml`, or any file containing a refresh token / developer token. The `.gitignore` covers the standard names.
- Prefer environment variables in MCP configs over on-disk JSON.
- Rotate refresh tokens periodically; revoke OAuth grants for any compromised key.
- The MCC `login_customer_id` is always sent — make sure your MCC's hierarchy reflects only the accounts you intend the AI to touch.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `USER_PERMISSION_DENIED` on a client account | Missing or wrong `login_customer_id` (must be the MCC, not the client) |
| `INVALID_FIELD_NAME` on metrics | Calling fields removed in v23 (e.g. `metrics.conversion_rate` → compute manually) |
| Extensions silently not appearing | You're hitting the legacy `ExtensionFeedItemService`. This fork uses the Asset API exclusively |
| `INVALID_CUSTOMER_ID` | Customer ID must be a 10-digit string with no dashes |
| `AUTHENTICATION_ERROR` | Refresh token expired or scope insufficient — re-run OAuth with `https://www.googleapis.com/auth/adwords` |

For raw debugging, the `run_gaql_query` tool gives you a direct GAQL escape hatch.

---

## License

MIT — see [LICENSE](LICENSE).

## v2.1 — Insights & Piloting Modules (2026-05-12)

**35 new tools** added across 10 modules, bringing the total to **129 tools**.

### New modules

- **Asset Performance** — `get_asset_performance_report` (RSA PerformanceLabel BEST/GOOD/LOW/PENDING)
- **Segments** — `get_demographic_performance`, `get_distance_performance`, `get_click_view`
- **Forecasting & Simulation** — `get_keyword_planner_forecast`, `get_keyword_bid_simulation`, `get_campaign_simulation`, `get_reach_forecast`
- **Customer Match** — `create_customer_match_list`, `upload_customer_match_users` (auto SHA-256 hashing)
- **Experiments** — `list_experiments`, `create_experiment`, `start_experiment`, `end_experiment`, `graduate_experiment`
- **Performance Max** — `create_pmax_campaign`, `create_asset_group`, `add_asset_group_signal`, `link_asset_to_asset_group`, `list_asset_groups`
- **Video & Demand Gen** — `create_video_campaign`, `create_demand_gen_campaign`, `upload_youtube_video_asset`
- **Shopping** — `list_merchant_center_links`, `create_shopping_campaign`, `get_product_performance`
- **Assets (Lead Forms / Promotions / Prices)** — `create_lead_form_asset`, `create_promotion_asset`, `create_price_asset`
- **Quota** — `get_api_quota_status`

### Insights extensions
- `list_recommendation_subscriptions`, `subscribe_to_recommendations`, `generate_audience_insights`

### Conversion extensions
- `create_conversion_value_rule`, `set_attribution_model`

### Cross-cutting safety
- **Dry-run mode** — set env `GADS_MCP_DRY_RUN=1` to make every mutating tool return a fake success without hitting the API. Useful for testing prompts and agent flows.
- **Audit log** — every mutation is appended to `./audit.log` (JSONL with before/after events). Override path with `GADS_MCP_AUDIT_LOG`.
- **`validate_only=True`** — exposed on `create_campaign` for server-side pre-flight validation.
- **Pagination** — `list_keywords` and `list_ads` now accept `limit` and `offset` parameters.

### Note on `get_auction_insights`
The per-competitor domain breakdown shown in the Google Ads UI ("Insights sur les enchères") is **not exposed via API v20**. This tool returns the next best thing: your own impression-share metrics plus an actionable diagnosis (rank-lost vs budget-lost percentages).

## Credits

- Original work: [grantweston/google-ads-mcp-complete](https://github.com/grantweston/google-ads-mcp-complete)
- This fork: [smartiesmb/google-ads-mcp-complete](https://github.com/smartiesmb/google-ads-mcp-complete) — additions for v23, conversion goals, keyword planner, asset removal, and production fixes.
