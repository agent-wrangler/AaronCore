---
name: "Weather"
description: "Check current conditions or a short forecast for a city."
default_prompt: "Check today's weather in Shanghai and tell me whether I need an umbrella."
---

# Weather

Check current conditions or a short forecast for a city. Use this skill when the user wants a practical weather answer rather than a travel guide or a long climate report.

## Good fit

- Current temperature, rain, wind, or general conditions
- A quick "do I need an umbrella or jacket" decision
- Today, tomorrow, or the next few days for a specific city

## Rules

- Confirm the city if it is missing or ambiguous.
- Default to current conditions plus a short forecast, not an hour-by-hour dump.
- End with a practical takeaway when the request implies travel, commuting, or going out.
- Keep the answer concrete and brief unless the user asks for more detail.

## Notes

This skill depends on live weather data. If the location cannot be resolved, ask for the city before continuing.
