# MLS Outreach Status

The club universe in `docs/mls-target-roles.csv` is anchored to the official MLS clubs directory:

- Source: https://www.mlssoccer.com/clubs/
- Verified coverage: all 30 MLS club sites listed by MLS as of June 19, 2026.

Current status:

- `docs/mls-target-roles.csv` is a target-role tracker, not a finished personal contact database.
- Person-level names, roles, and email addresses must be verified from current official club staff pages, club press releases, LinkedIn profiles, or publicly listed staff directories before outreach.
- Do not guess email formats or infer private addresses.
- If no public email exists, use the verified person name plus official profile/contact route and mark `email_status` as `not_public`.

GTM rule:

- The product can be trialed locally without this list.
- A club outreach campaign is not GTM-ready until every row has a verified current person or an explicit `not_public` contact status.
