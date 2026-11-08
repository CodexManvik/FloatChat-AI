## FloatChat evaluation — 29/30 questions fully correct

Run against `https://floatchat-ai-svjw.onrender.com` on 2026-11-08 18:16 UTC.

| Metric | Score |
|---|---|
| Routing accuracy (SQL vs search, and which analysis) | 97% |
| Filter accuracy (region, month, year, sensor) | 100% |
| Answer checks passed | 100% |
| Median latency | 2595 ms |
| Understood by the LLM router | 28/30 |
| Answers written by the LLM | 30/30 |

| Case | Question | Routing | Filters | Answer | Notes |
|---|---|---|---|---|---|
| `depth-avg` | What is the average temperature at different depths? | ✅ | ✅ | ✅ |  |
| `depth-avg-arabian` | What is the average temperature at different depths in the Arabian Sea? | ✅ | ✅ | ✅ |  |
| `depth-avg-bengal-march` | Average salinity by depth in the Bay of Bengal in March 2026 | ✅ | ✅ | ✅ |  |
| `regions` | Compare surface temperature across ocean regions | ✅ | ✅ | ✅ |  |
| `regions-warmest` | Which region has the highest average temperature in the upper ocean? | ✅ | ✅ | ✅ |  |
| `layers` | Show temperature and salinity by depth layer | ✅ | ✅ | ✅ |  |
| `layers-southern` | Compare surface and deep water in the Southern Indian Ocean | ✅ | ✅ | ✅ |  |
| `monthly` | Show the monthly trend of surface temperature | ✅ | ✅ | ✅ |  |
| `monthly-equator` | How has the average temperature near the equator changed over time? | ✅ | ✅ | ✅ |  |
| `floats-active` | Give me a summary of the most active floats | ✅ | ✅ | ✅ |  |
| `floats-arabian` | Summarize the floats operating in the Arabian Sea | ✅ | ✅ | ✅ |  |
| `bgc-oxygen` | Average dissolved oxygen by ocean zone | ✅ | ✅ | ✅ |  |
| `bgc-chlorophyll-bengal` | Compare chlorophyll levels across zones in the Bay of Bengal | ✅ | ✅ | ✅ |  |
| `bgc-ph` | What is the average pH in each ocean zone? | ✅ | ✅ | ✅ |  |
| `count-arabian` | How many profiles were recorded in the Arabian Sea? | ✅ | ✅ | ✅ |  |
| `max-bengal-2026` | What was the maximum temperature recorded in the Bay of Bengal in 2026? | ✅ | ✅ | ✅ |  |
| `mean-salinity-1000m` | What is the mean salinity at 1000 m? | ✅ | ✅ | ✅ |  |
| `find-equator-march` | Show me salinity profiles near the equator in March 2026 | ✅ | ✅ | ✅ |  |
| `find-low-oxygen` | Which floats measured low oxygen in the Arabian Sea? | ✅ | ✅ | ✅ |  |
| `find-bengal` | Find profiles from the Bay of Bengal | ✅ | ✅ | ✅ |  |
| `find-chlorophyll-southern` | Show me floats with chlorophyll sensors in the Southern Indian Ocean | ✅ | ✅ | ✅ |  |
| `find-indonesia-january` | Profiles near Indonesia in January 2026 | ✅ | ✅ | ✅ |  |
| `no-data-red-sea` | Describe recent profiles from the Red Sea | ✅ | ✅ | ✅ |  |
| `find-nitrate-arabian` | Find nitrate measurements in the Arabian Sea | ✅ | ✅ | ✅ |  |
| `find-thermocline` | Show me profiles with a strong thermocline | ✅ | ✅ | ✅ |  |
| `find-bengal-september` | Profiles in the Bay of Bengal in September 2026 | ❌ | ✅ | ✅ | routed to analytical/custom |
| `follow-region` | now only the Bay of Bengal *(follow-up to depth-avg)* | ✅ | ✅ | ✅ |  |
| `follow-month` | and just in March *(follow-up to depth-avg-arabian)* | ✅ | ✅ | ✅ |  |
| `follow-monthly-arabian` | now for the Arabian Sea *(follow-up to monthly)* | ✅ | ✅ | ✅ |  |
| `follow-oxygen` | only the ones measuring oxygen *(follow-up to find-bengal)* | ✅ | ✅ | ✅ |  |
