# Location seed cleanup proposals

Generated from `data/seeds/**/*.xlsx` **Where** values.

**How to use**

1. Review **high** confidence clusters first (safe renames in seeds / Combine in app).
2. Review **medium** (prefix families like Preston*). Decide one keeper name.
3. Treat **low** as hints only; many are distinct venues that share a first word.
4. Suggested keeper = most frequent spelling in that cluster (not always the best map name).

Updating seeds replaces Where text for future imports / fresh DBs.
It does **not** move lat/lon. Clean production Locations in the UI for pins.

## demo

- Distinct locations: **638**
- Rows with a Where value: **1887**

Clusters: 12 high, 42 medium, 20 low

### High confidence

#### 1. Keep `Home - dining room` (80 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 78 | Home - dining room **keeper** |
| 2 | Home - Dining room |

#### 2. Keep `Home - Patio` (44 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 33 | Home - Patio **keeper** |
| 11 | Home - patio |

#### 3. Keep `Cafe 50's` (35 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 31 | Cafe 50's **keeper** |
| 4 | Café 50's |

#### 4. Keep `IHOP, MDR` (11 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 7 | IHOP, MDR **keeper** |
| 2 | Ihop, MDR |
| 2 | iHop, MDR |

#### 5. Keep `Café 50s` (10 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 8 | Café 50s **keeper** |
| 2 | Cafe 50s |

#### 6. Keep `Café 50's, Venice` (7 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 6 | Café 50's, Venice **keeper** |
| 1 | Cafe 50's, Venice |

#### 7. Keep `La Cabaña, Venice` (7 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 4 | La Cabaña, Venice **keeper** |
| 2 | La Cabana, Venice |
| 1 | La Cabańa, Venice |

#### 8. Keep `J Nichols, MDR` (7 rows)

same fuzzy form (punctuation/spacing)

| Count | Variant |
|------:|---------|
| 4 | J Nichols, MDR **keeper** |
| 3 | J. Nichols, MDR |

#### 9. Keep `Café 50s, Venice` (5 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 4 | Café 50s, Venice **keeper** |
| 1 | Cafe 50s, Venice |

#### 10. Keep `Home, Patio` (4 rows)

same fuzzy form (punctuation/spacing)

| Count | Variant |
|------:|---------|
| 3 | Home, Patio **keeper** |
| 1 | Home -patio |

#### 11. Keep `Shoop’s, Santa Monica` (3 rows)

same fuzzy form (punctuation/spacing)

| Count | Variant |
|------:|---------|
| 2 | Shoop’s, Santa Monica **keeper** |
| 1 | Shoops, Santa Monica |

#### 12. Keep `Duke's Huntington Beach` (2 rows)

same fuzzy form (punctuation/spacing)

| Count | Variant |
|------:|---------|
| 1 | Duke's Huntington Beach **keeper** |
| 1 | Duke's, Huntington Beach |

### Medium confidence

#### 1. Keep `Home - Island` (358 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 303 | Home - Island **keeper** |
| 55 | Home |

#### 2. Keep `Preston` (210 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 208 | Preston **keeper** |
| 1 | Preston - Passover |
| 1 | Preston Way dining room |

#### 3. Keep `Home - kitchen` (34 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 33 | Home - kitchen **keeper** |
| 1 | Home - kitchen (thinking of J Nichol's) |

#### 4. Keep `George's` (27 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 11 | George's **keeper** |
| 7 | George's, Santa Monica |
| 5 | George's, Venice |
| 3 | George's Burgers |
| 1 | George's (Café 50s fire last night!) |

#### 5. Keep `Home - diving board table` (16 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 15 | Home - diving board table **keeper** |
| 1 | Home - diving board |

#### 6. Keep `Dakota Trail` (11 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 10 | Dakota Trail **keeper** |
| 1 | Dakota |

#### 7. Keep `Westside Tavern` (11 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 5 | Westside Tavern **keeper** |
| 4 | Westside Tavern, WLA |
| 1 | Westside Tavern after movie 'Boyhood'. |
| 1 | Westside Tavern, WLA w/Michael & Shannon |

#### 8. Keep `Centanni` (9 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 7 | Centanni **keeper** |
| 2 | Centanni, Venice |

#### 9. Keep `Bob's Big Boy, Calimesa` (7 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 4 | Bob's Big Boy, Calimesa **keeper** |
| 3 | Bob's Big Boy |

#### 10. Keep `Clutch, Venice` (5 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 4 | Clutch, Venice **keeper** |
| 1 | Clutch |

#### 11. Keep `Superba Bread & Food, Venice` (5 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 4 | Superba Bread & Food, Venice **keeper** |
| 1 | Superba Bread & Food |

#### 12. Keep `Carpenteria` (5 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 3 | Carpenteria **keeper** |
| 2 | Carpenteria State Beach #106 |

#### 13. Keep `Jawbone` (4 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 3 | Jawbone **keeper** |
| 1 | Jawbone Canyon, CA |

#### 14. Keep `Tahoe Valley Campground` (4 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 3 | Tahoe Valley Campground **keeper** |
| 1 | Tahoe Valley Campground #147 - Calrisian |

#### 15. Keep `Newport Dunes` (4 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | Newport Dunes **keeper** |
| 2 | Newport Dunes RV Park |

#### 16. Keep `Carpinteria State Beach #357` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | Carpinteria State Beach #357 **keeper** |
| 1 | Carpinteria State Beach |

#### 17. Keep `Huntington Beach` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | Huntington Beach **keeper** |
| 1 | Huntington Beach, CA |

#### 18. Keep `Paris` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | Paris **keeper** |
| 1 | Paris Baguette, West Covina |

#### 19. Keep `Penmar` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | Penmar **keeper** |
| 1 | Penmar Golf Course |

#### 20. Keep `San Clemente St Beach` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | San Clemente St Beach **keeper** |
| 1 | San Clemente |

#### 21. Keep `Swingers, Santa Monica` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | Swingers, Santa Monica **keeper** |
| 1 | Swingers |

#### 22. Keep `The Penmar, Venice` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | The Penmar, Venice **keeper** |
| 1 | The Penmar |

#### 23. Keep `George’s` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | George’s **keeper** |
| 1 | George’s, Santa Monica |
| 1 | George’s, Venice |

#### 24. Keep `In-N-Out` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | In-N-Out **keeper** |
| 1 | In-N-Out, Ontario, CA |
| 1 | In-n-Out, Westwood |

#### 25. Keep `Spitfire` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Spitfire **keeper** |
| 1 | Spitfire, Santa Monica |
| 1 | Spitfire, Santa Monica - Closing day |

#### 26. Keep `Watergrill` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Watergrill **keeper** |
| 1 | Watergrill, Santa Monica |
| 1 | Watergrill, SM |

#### 27. Keep `Yardhouse` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Yardhouse **keeper** |
| 1 | Yardhouse, MDR |
| 1 | Yardhouse, Rancho Mirage |

#### 28. Keep `Backyard` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Backyard **keeper** |
| 1 | Backyard, Venice |

#### 29. Keep `Bridgeport` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Bridgeport **keeper** |
| 1 | Bridgeport Resevoir |

#### 30. Keep `Calico - Mule Canyon Road` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Calico - Mule Canyon Road **keeper** |
| 1 | Calico - Mule Canyon Road 9:9 |

#### 31. Keep `Casablanca` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Casablanca **keeper** |
| 1 | Casablanca, Venice |

#### 32. Keep `Indian Wells` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Indian Wells **keeper** |
| 1 | Indian Wells pool |

#### 33. Keep `Islands, Marina Del Rey` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Islands, Marina Del Rey **keeper** |
| 1 | Island’s |

#### 34. Keep `Keedy's` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Keedy's **keeper** |
| 1 | Keedy's, La Quinta |

#### 35. Keep `Maple Block` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Maple Block **keeper** |
| 1 | Maple Block, Culver City |

#### 36. Keep `Morro Bay` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Morro Bay **keeper** |
| 1 | Morro Bay State Beach |

#### 37. Keep `Nichols` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Nichols **keeper** |
| 1 | Nichols, Marina Del Rey |

#### 38. Keep `Port Angeles, WA` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Port Angeles, WA **keeper** |
| 1 | Port Angeles, WA - Victoria, BC Ferry |

#### 39. Keep `Rutt's` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Rutt's **keeper** |
| 1 | Rutt's, Culver City |

#### 40. Keep `The Mar Vista` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | The Mar Vista **keeper** |
| 1 | The Mar Vista, Mar Vista |

#### 41. Keep `Twoheys` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Twoheys **keeper** |
| 1 | Twohey’s (last day) |

#### 42. Keep `Upper West` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Upper West **keeper** |
| 1 | Upper West, WLA on Pico |

### Low confidence (review)

#### 1. Keep `Venice Bistro, Venice, CA` (5 rows)

share leading token 'venice' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Venice Bistro, Venice, CA **keeper** |
| 1 | Venice Beach Bar and Kitchen |
| 1 | Venice Beach Club, @Rose |
| 1 | Venice Cucina on Nancy's 6th AA Bday |

#### 2. Keep `Killer Cafe, MDR` (5 rows)

share leading token 'killer' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Killer Cafe, MDR **keeper** |
| 2 | Killer Shrimp Cafe, MDR |
| 1 | Killer Cafe, Marina Del Rey |

#### 3. Keep `Tahoe - Steamers` (5 rows)

share leading token 'tahoe' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Tahoe - Steamers **keeper** |
| 2 | Tahoe City Campground |
| 1 | Tahoe - Sonora Pass |

#### 4. Keep `Sunset Vista Campground, Huntington Beach` (4 rows)

share leading token 'sunset' (manual review)

| Count | Variant |
|------:|---------|
| 3 | Sunset Vista Campground, Huntington Beach **keeper** |
| 1 | Sunset Park, Las Vegas, NV |

#### 5. Keep `Clearman's North Woods Inn, La Mirada ￼` (4 rows)

share leading token 'clearman's' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Clearman's North Woods Inn, La Mirada ￼ **keeper** |
| 1 | Clearman's Galley, The Boat, Rosemead, CA |
| 1 | Clearman's Northwoods inn, Santa Ana |

#### 6. Keep `Terrace Cafe, MDR` (3 rows)

share leading token 'terrace' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Terrace Cafe, MDR **keeper** |
| 1 | Terrace Café, Marina Del Rey |
| 1 | Terrace, MDR |

#### 7. Keep `Denny's, Cerritos` (3 rows)

share leading token 'denny's' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Denny's, Cerritos **keeper** |
| 1 | Denny's, Grapevine, CA |
| 1 | Denny's, Hacienda Heights |

#### 8. Keep `Norms, West Covina` (3 rows)

share leading token 'norms' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Norms, West Covina **keeper** |
| 1 | Norms, West Hollywood |
| 1 | Norms, WLA |

#### 9. Keep `Burgers and Beer, Santa Monica, CA` (3 rows)

share leading token 'burgers' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Burgers and Beer, Santa Monica, CA **keeper** |
| 1 | Burgers and Brew, Venice |
| 1 | Burgers n Brew, Santa Monica |

#### 10. Keep `Corky's, Fontana` (3 rows)

share leading token 'corky's' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Corky's, Fontana **keeper** |
| 1 | Corky's, Sherman Oaks |

#### 11. Keep `Teddy's Diner` (3 rows)

share leading token 'teddy's' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Teddy's Diner **keeper** |
| 1 | Teddy's, West L.A. |

#### 12. Keep `Perry’s, Santa Monica` (3 rows)

share leading token 'perrys' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Perry’s, Santa Monica **keeper** |
| 1 | Perry’s Beach Cafe, Santa Monica |

#### 13. Keep `Superba Bread and Food, Venice` (3 rows)

share leading token 'superba' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Superba Bread and Food, Venice **keeper** |
| 1 | Superba, Venice |

#### 14. Keep `Campland by the Bay, San Diego` (3 rows)

share leading token 'campland' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Campland by the Bay, San Diego **keeper** |
| 1 | Campland in the RV |
| 1 | Campland, San Diego, Nancy’s birthday and Parrot Head |

#### 15. Keep `Tacos Por Favor` (3 rows)

share leading token 'tacos' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Tacos Por Favor **keeper** |
| 1 | Tacos Tamix, Pacific Ave, Venice |

#### 16. Keep `Harris Ranch steakhouse, Cailinga￼` (3 rows)

share leading token 'harris' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Harris Ranch steakhouse, Cailinga￼ **keeper** |
| 1 | Harris Ranch, Cailinga￼ |
| 1 | Harris Ranch, Coalinga |

#### 17. Keep `Victoria, BC` (3 rows)

share leading token 'victoria' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Victoria, BC **keeper** |
| 1 | Victoria /Port Angeles Ferry |

#### 18. Keep `Mañana Cafe, Culver City` (3 rows)

share leading token 'manana' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Mañana Cafe, Culver City **keeper** |
| 1 | Mañana Café, Venice |
| 1 | Mañana, Culver City |

#### 19. Keep `Tender Greens, MDR - Goodbye Louie 💙` (2 rows)

share leading token 'tender' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Tender Greens, MDR - Goodbye Louie 💙 **keeper** |
| 1 | Tender Tenders, Marina Del Rey |

#### 20. Keep `Little Branch Cafe, Chicago` (2 rows)

share leading token 'little' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Little Branch Cafe, Chicago **keeper** |
| 1 | Little Fatty, Mar Vista, CA |

### Top 30 by frequency

| Count | Name |
|------:|------|
| 303 | Home - Island |
| 208 | Preston |
| 129 | Superior |
| 78 | Home - dining room |
| 68 | Zinque, Venice |
| 55 | Home |
| 33 | Home - kitchen |
| 33 | Home - Patio |
| 33 | Palm Desert |
| 31 | Cafe 50's |
| 20 | Home - pad patio |
| 15 | Home - diving board table |
| 12 | Home - RV |
| 11 | George's |
| 11 | Home - patio |
| 10 | Dakota Trail |
| 10 | Sally's |
| 8 | Café 50s |
| 7 | Centanni |
| 7 | IHOP, MDR |
| 7 | George's, Santa Monica |
| 7 | J Nichols |
| 6 | Café 50's, Venice |
| 6 | Freedom Park, Palm Desert, CA |
| 5 | Westside Tavern |
| 5 | George's, Venice |
| 5 | Maxine's |
| 5 | Campground by the Lake, Tahoe |
| 5 | Lake Tahoe Campground |
| 4 | Abbot's Habit |

## manpearl_seed

- Distinct locations: **628**
- Rows with a Where value: **1944**

Clusters: 13 high, 40 medium, 21 low

### High confidence

#### 1. Keep `Home - dining room` (80 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 78 | Home - dining room **keeper** |
| 2 | Home - Dining room |

#### 2. Keep `Home - Patio` (44 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 33 | Home - Patio **keeper** |
| 11 | Home - patio |

#### 3. Keep `Cafe 50's` (29 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 25 | Cafe 50's **keeper** |
| 4 | Café 50's |

#### 4. Keep `Café 50s` (11 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 9 | Café 50s **keeper** |
| 2 | Cafe 50s |

#### 5. Keep `IHOP, MDR` (11 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 7 | IHOP, MDR **keeper** |
| 2 | Ihop, MDR |
| 2 | iHop, MDR |

#### 6. Keep `Café 50's, Venice` (8 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 6 | Café 50's, Venice **keeper** |
| 2 | Cafe 50's, Venice |

#### 7. Keep `La Cabaña, Venice` (7 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 4 | La Cabaña, Venice **keeper** |
| 2 | La Cabana, Venice |
| 1 | La Cabańa, Venice |

#### 8. Keep `Café 50s, Venice` (6 rows)

same normalized_name (accent/case/spacing)

| Count | Variant |
|------:|---------|
| 5 | Café 50s, Venice **keeper** |
| 1 | Cafe 50s, Venice |

#### 9. Keep `J. Nichols, MDR` (5 rows)

same fuzzy form (punctuation/spacing)

| Count | Variant |
|------:|---------|
| 3 | J. Nichols, MDR **keeper** |
| 2 | J Nichols, MDR |

#### 10. Keep `Home, Patio` (4 rows)

same fuzzy form (punctuation/spacing)

| Count | Variant |
|------:|---------|
| 3 | Home, Patio **keeper** |
| 1 | Home -patio |

#### 11. Keep `Home, Kitchen` (3 rows)

same fuzzy form (punctuation/spacing)

| Count | Variant |
|------:|---------|
| 2 | Home, Kitchen **keeper** |
| 1 | Home Kitchen |

#### 12. Keep `Shoop’s, Santa Monica` (3 rows)

same fuzzy form (punctuation/spacing)

| Count | Variant |
|------:|---------|
| 2 | Shoop’s, Santa Monica **keeper** |
| 1 | Shoops, Santa Monica |

#### 13. Keep `Duke's Huntington Beach` (2 rows)

same fuzzy form (punctuation/spacing)

| Count | Variant |
|------:|---------|
| 1 | Duke's Huntington Beach **keeper** |
| 1 | Duke's, Huntington Beach |

### Medium confidence

#### 1. Keep `Home - Island` (354 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 303 | Home - Island **keeper** |
| 51 | Home |

#### 2. Keep `Preston` (262 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 260 | Preston **keeper** |
| 1 | Preston - Passover |
| 1 | Preston Way dining room |

#### 3. Keep `Home - kitchen` (34 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 33 | Home - kitchen **keeper** |
| 1 | Home - kitchen (thinking of J Nichol's) |

#### 4. Keep `Sally's` (27 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 24 | Sally's **keeper** |
| 3 | Sally |

#### 5. Keep `George's` (27 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 11 | George's **keeper** |
| 7 | George's, Santa Monica |
| 5 | George's, Venice |
| 3 | George's Burgers |
| 1 | George's (Café 50s fire last night!) |

#### 6. Keep `Home - diving board table` (16 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 15 | Home - diving board table **keeper** |
| 1 | Home - diving board |

#### 7. Keep `Dakota Trail` (12 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 11 | Dakota Trail **keeper** |
| 1 | Dakota |

#### 8. Keep `Centanni` (8 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 6 | Centanni **keeper** |
| 2 | Centanni, Venice |

#### 9. Keep `Westside Tavern, WLA` (8 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 4 | Westside Tavern, WLA **keeper** |
| 3 | Westside Tavern |
| 1 | Westside Tavern, WLA w/Michael & Shannon |

#### 10. Keep `Carpenteria` (6 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 4 | Carpenteria **keeper** |
| 2 | Carpenteria State Beach #106 |

#### 11. Keep `Superba Bread & Food, Venice` (5 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 4 | Superba Bread & Food, Venice **keeper** |
| 1 | Superba Bread & Food |

#### 12. Keep `Clutch, Venice` (5 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 3 | Clutch, Venice **keeper** |
| 1 | Clutch |
| 1 | Clutch, Venice (six days after opening) |

#### 13. Keep `Swingers, Santa Monica` (5 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 3 | Swingers, Santa Monica **keeper** |
| 2 | Swingers |

#### 14. Keep `Indian Wells` (4 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 3 | Indian Wells **keeper** |
| 1 | Indian Wells pool |

#### 15. Keep `Jawbone` (4 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 3 | Jawbone **keeper** |
| 1 | Jawbone Canyon, CA |

#### 16. Keep `Tahoe Valley Campground` (4 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 3 | Tahoe Valley Campground **keeper** |
| 1 | Tahoe Valley Campground #147 - Calrisian |

#### 17. Keep `Newport Dunes` (4 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | Newport Dunes **keeper** |
| 2 | Newport Dunes RV Park |

#### 18. Keep `Carpinteria State Beach #357` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | Carpinteria State Beach #357 **keeper** |
| 1 | Carpinteria State Beach |

#### 19. Keep `Huntington Beach` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | Huntington Beach **keeper** |
| 1 | Huntington Beach, CA |

#### 20. Keep `Penmar` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | Penmar **keeper** |
| 1 | Penmar Golf Course |

#### 21. Keep `San Clemente St Beach` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | San Clemente St Beach **keeper** |
| 1 | San Clemente |

#### 22. Keep `The Penmar, Venice` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 2 | The Penmar, Venice **keeper** |
| 1 | The Penmar |

#### 23. Keep `George’s` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | George’s **keeper** |
| 1 | George’s, Santa Monica |
| 1 | George’s, Venice |

#### 24. Keep `In-N-Out` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | In-N-Out **keeper** |
| 1 | In-N-Out, Ontario, CA |
| 1 | In-n-Out, Westwood |

#### 25. Keep `Spitfire` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Spitfire **keeper** |
| 1 | Spitfire, Santa Monica |
| 1 | Spitfire, Santa Monica - Closing day |

#### 26. Keep `Yardhouse` (3 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Yardhouse **keeper** |
| 1 | Yardhouse, MDR |
| 1 | Yardhouse, Rancho Mirage |

#### 27. Keep `Backyard` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Backyard **keeper** |
| 1 | Backyard, Venice |

#### 28. Keep `Bridgeport` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Bridgeport **keeper** |
| 1 | Bridgeport Resevoir |

#### 29. Keep `Calico - Mule Canyon Road` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Calico - Mule Canyon Road **keeper** |
| 1 | Calico - Mule Canyon Road 9:9 |

#### 30. Keep `Casablanca` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Casablanca **keeper** |
| 1 | Casablanca, Venice |

#### 31. Keep `Islands, Marina Del Rey` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Islands, Marina Del Rey **keeper** |
| 1 | Island’s |

#### 32. Keep `Keedy's` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Keedy's **keeper** |
| 1 | Keedy's, La Quinta |

#### 33. Keep `Maple Block` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Maple Block **keeper** |
| 1 | Maple Block, Culver City |

#### 34. Keep `Morro Bay` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Morro Bay **keeper** |
| 1 | Morro Bay State Beach |

#### 35. Keep `Nichols` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Nichols **keeper** |
| 1 | Nichols, Marina Del Rey |

#### 36. Keep `Port Angeles, WA` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Port Angeles, WA **keeper** |
| 1 | Port Angeles, WA - Victoria, BC Ferry |

#### 37. Keep `Rutt's` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Rutt's **keeper** |
| 1 | Rutt's, Culver City |

#### 38. Keep `The Mar Vista` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | The Mar Vista **keeper** |
| 1 | The Mar Vista, Mar Vista |

#### 39. Keep `Twoheys` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Twoheys **keeper** |
| 1 | Twohey’s (last day) |

#### 40. Keep `Upper West` (2 rows)

prefix/extension variants (e.g. Preston vs Preston Passover)

| Count | Variant |
|------:|---------|
| 1 | Upper West **keeper** |
| 1 | Upper West, WLA on Pico |

### Low confidence (review)

#### 1. Keep `Bob's Big Boy, Calimesa` (6 rows)

share leading token 'bob's' (manual review)

| Count | Variant |
|------:|---------|
| 4 | Bob's Big Boy, Calimesa **keeper** |
| 1 | Bob's Big Boy, Calemesa |
| 1 | Bob's Big Boy, L.A. on Wilshire |

#### 2. Keep `Killer Cafe, MDR` (5 rows)

share leading token 'killer' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Killer Cafe, MDR **keeper** |
| 2 | Killer Shrimp Cafe, MDR |
| 1 | Killer Cafe, Marina Del Rey |

#### 3. Keep `Campland on the Bay, San Diego` (5 rows)

share leading token 'campland' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Campland on the Bay, San Diego **keeper** |
| 1 | Campland by the Bay, San Diego |
| 1 | Campland in the RV |
| 1 | Campland, San Diego, Nancy’s birthday and Parrot Head |

#### 4. Keep `Tahoe - Steamers` (5 rows)

share leading token 'tahoe' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Tahoe - Steamers **keeper** |
| 2 | Tahoe City Campground |
| 1 | Tahoe - Sonora Pass |

#### 5. Keep `Venice Beach Bar and Kitchen` (4 rows)

share leading token 'venice' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Venice Beach Bar and Kitchen **keeper** |
| 1 | Venice Beach Club, @Rose |
| 1 | Venice Bistro, Venice, CA |
| 1 | Venice Cucina on Nancy's 6th AA Bday |

#### 6. Keep `Clearman's North Woods Inn, La Mirada ￼` (4 rows)

share leading token 'clearman's' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Clearman's North Woods Inn, La Mirada ￼ **keeper** |
| 1 | Clearman's Galley, The Boat, Rosemead, CA |
| 1 | Clearman's Northwoods inn, Santa Ana |

#### 7. Keep `Watergrill, Santa Monica` (3 rows)

share leading token 'watergrill' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Watergrill, Santa Monica **keeper** |
| 1 | Watergrill, SM |

#### 8. Keep `Terrace Cafe, MDR` (3 rows)

share leading token 'terrace' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Terrace Cafe, MDR **keeper** |
| 1 | Terrace Café, Marina Del Rey |
| 1 | Terrace, MDR |

#### 9. Keep `Denny's, Cerritos` (3 rows)

share leading token 'denny's' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Denny's, Cerritos **keeper** |
| 1 | Denny's, Grapevine, CA |
| 1 | Denny's, Hacienda Heights |

#### 10. Keep `Norms, West Covina` (3 rows)

share leading token 'norms' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Norms, West Covina **keeper** |
| 1 | Norms, West Hollywood |
| 1 | Norms, WLA |

#### 11. Keep `Burgers and Beer, Santa Monica, CA` (3 rows)

share leading token 'burgers' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Burgers and Beer, Santa Monica, CA **keeper** |
| 1 | Burgers and Brew, Venice |
| 1 | Burgers n Brew, Santa Monica |

#### 12. Keep `Corky's, Fontana` (3 rows)

share leading token 'corky's' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Corky's, Fontana **keeper** |
| 1 | Corky's, Sherman Oaks |

#### 13. Keep `Teddy's Diner` (3 rows)

share leading token 'teddy's' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Teddy's Diner **keeper** |
| 1 | Teddy's, West L.A. |

#### 14. Keep `Perry’s, Santa Monica` (3 rows)

share leading token 'perrys' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Perry’s, Santa Monica **keeper** |
| 1 | Perry’s Beach Cafe, Santa Monica |

#### 15. Keep `Superba Bread and Food, Venice` (3 rows)

share leading token 'superba' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Superba Bread and Food, Venice **keeper** |
| 1 | Superba, Venice |

#### 16. Keep `Tacos Por Favor` (3 rows)

share leading token 'tacos' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Tacos Por Favor **keeper** |
| 1 | Tacos Tamix, Pacific Ave, Venice |

#### 17. Keep `Harris Ranch steakhouse, Cailinga￼` (3 rows)

share leading token 'harris' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Harris Ranch steakhouse, Cailinga￼ **keeper** |
| 1 | Harris Ranch, Cailinga￼ |
| 1 | Harris Ranch, Coalinga |

#### 18. Keep `Victoria, BC` (3 rows)

share leading token 'victoria' (manual review)

| Count | Variant |
|------:|---------|
| 2 | Victoria, BC **keeper** |
| 1 | Victoria /Port Angeles Ferry |

#### 19. Keep `Mañana Cafe, Culver City` (3 rows)

share leading token 'manana' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Mañana Cafe, Culver City **keeper** |
| 1 | Mañana Café, Venice |
| 1 | Mañana, Culver City |

#### 20. Keep `Tender Greens, MDR - Goodbye Louie 💙` (2 rows)

share leading token 'tender' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Tender Greens, MDR - Goodbye Louie 💙 **keeper** |
| 1 | Tender Tenders, Marina Del Rey |

#### 21. Keep `Little Branch Cafe, Chicago` (2 rows)

share leading token 'little' (manual review)

| Count | Variant |
|------:|---------|
| 1 | Little Branch Cafe, Chicago **keeper** |
| 1 | Little Fatty, Mar Vista, CA |

### Top 30 by frequency

| Count | Name |
|------:|------|
| 303 | Home - Island |
| 260 | Preston |
| 146 | Superior |
| 78 | Home - dining room |
| 68 | Zinque, Venice |
| 51 | Home |
| 39 | Palm Desert |
| 33 | Home - kitchen |
| 33 | Home - Patio |
| 25 | Cafe 50's |
| 24 | Sally's |
| 20 | Home - pad patio |
| 15 | Home - diving board table |
| 12 | Home - RV |
| 11 | Dakota Trail |
| 11 | George's |
| 11 | Home - patio |
| 9 | Café 50s |
| 7 | IHOP, MDR |
| 7 | George's, Santa Monica |
| 7 | J Nichols |
| 6 | Centanni |
| 6 | Café 50's, Venice |
| 5 | Café 50s, Venice |
| 5 | George's, Venice |
| 5 | Maxine's |
| 5 | Campground by the Lake, Tahoe |
| 5 | Lake Tahoe Campground |
| 4 | Carpenteria |
| 4 | Superba Bread & Food, Venice |

## Per-file distinct locations

### `data/seeds/backgammon/backgammon_demo_2026-06-22.xlsx`

6 Where cells, 4 distinct.

| Count | Name |
|------:|------|
| 3 | Beach tables |
| 1 | Patio |
| 1 | Mom's House |
| 1 | Carpenteria |

### `data/seeds/backgammon/backgammon_seed_2026-06-16.xlsx`

5 Where cells, 2 distinct.

| Count | Name |
|------:|------|
| 3 | Sally |
| 2 | Carpenteria |

### `data/seeds/dominos/dominos_demo_2026-06-22.xlsx`

1417 Where cells, 579 distinct.

| Count | Name |
|------:|------|
| 303 | Home - Island |
| 78 | Home - dining room |
| 68 | Zinque, Venice |
| 55 | Home |
| 33 | Home - kitchen |
| 33 | Home - Patio |
| 31 | Cafe 50's |
| 20 | Home - pad patio |
| 15 | Home - diving board table |
| 12 | Home - RV |
| 11 | George's |
| 11 | Home - patio |
| 10 | Dakota Trail |
| 8 | Café 50s |
| 7 | Centanni |
| 7 | IHOP, MDR |
| 7 | George's, Santa Monica |
| 7 | J Nichols |
| 6 | Café 50's, Venice |
| 5 | Westside Tavern |
| 5 | George's, Venice |
| 5 | Maxine's |
| 5 | Campground by the Lake, Tahoe |
| 4 | Abbot's Habit |
| 4 | J Nichols, MDR |
| 4 | Café 50s, Venice |
| 4 | Clutch, Venice |
| 4 | Superba Bread & Food, Venice |
| 4 | Bob's Big Boy, Calimesa |
| 4 | Café 50's |
| 4 | La Cabaña |
| 4 | Westside Tavern, WLA |
| 4 | La Cabaña, Venice |
| 4 | Hal Burns Truck, Santa Fe, NM |
| 3 | Bob's Big Boy |
| 3 | J. Nichols, MDR |
| 3 | Pann's |
| 3 | George's Burgers |
| 3 | Swinger's, Santa Monica |
| 3 | Sidewalk Cafe, Venice |
| 3 | Tahoe Valley Campground |
| 3 | Jawbone |
| 3 | Sunset Vista Campground, Huntington Beach |
| 3 | Johnnie's Pastrami |
| 3 | Home, Patio |
| 3 | The Spot, Carpinteria |
| 2 | Paris |
| 2 | Engine Co. 28 |
| 2 | Venice Bistro, Venice, CA |
| 2 | Pitfire |
| 2 | Literati cafe |
| 2 | IHOP, Marina Del Rey |
| 2 | Bossa Nova, WLA |
| 2 | Centanni, Venice |
| 2 | Killer Shrimp Cafe, MDR |
| 2 | Ruth's Chris, MDR |
| 2 | Cafe 50s |
| 2 | Swingers, Santa Monica |
| 2 | Izzy's Deli, Santa Monica |
| 2 | Rustic Kitchen |
| 2 | Le Pain Quotidien |
| 2 | La Cabana, Venice |
| 2 | Busy Bee, Ventura |
| 2 | Killer Cafe, MDR |
| 2 | Perry’s, Santa Monica |
| 2 | Shoop’s, Santa Monica |
| 2 | Dinah’s |
| 2 | Superba Bread and Food, Venice |
| 2 | Port Hueneme |
| 2 | Johnny’s Pastrami |
| 2 | San Clemente St Beach |
| 2 | Steamers |
| 2 | Home - Landau |
| 2 | Tahoe - Steamers |
| 2 | South Lake Tahoe, 4th St |
| 2 | Carpenteria State Beach #106 |
| 2 | Carpinteria State Beach #357 |
| 2 | Home, Kitchen |
| 2 | Mel's Diner, Santa Monica |
| 2 | Gold Sands Casino RV Park, Carson City, NV |
| 2 | Bishop, CA |
| 2 | Moose Lodge, SLT |
| 2 | Home - Dining room |
| 2 | Ihop, MDR |
| 2 | Blueys |
| 2 | Faria State Park #18, Ventura |
| 2 | Corky's, Fontana |
| 2 | Clearman's North Woods Inn, La Mirada ￼ |
| 2 | Saby's |
| 2 | Penmar |
| 2 | Companion, Venice |
| 2 | Tapiola Park, Asteria, OR |
| 2 | Mora Campground, La Puch, WA |
| 2 | Victoria, BC |
| 2 | Ladysmith, BC |
| 2 | Teddy's Diner |
| 2 | Dinah's |
| 2 | iHop, Sepulveda, Culver City |
| 2 | The Manchester |
| 2 | Esau's, Carpinteria |
| 2 | Elysee Bakery and Café, Westwood |
| 2 | Rockinwagner |
| 2 | iHop, MDR |
| 2 | Tacos Por Favor |
| 2 | The Penmar, Venice |
| 2 | Urban Plates |
| 2 | Malibu |
| 2 | Newport Dunes RV Park |
| 1 | Spitfire, Santa Monica |
| 1 | On Montana |
| 1 | Backyard |
| 1 | Upper West |
| 1 | Wurshkuke, Venice |
| 1 | Backyard, Venice |
| 1 | 101 Cafe, Hollywood |
| 1 | Solerno beach |
| 1 | Abbott's Habit |
| 1 | Maxwells |
| 1 | Watergrill |
| 1 | Rick's Tavern, Santa Monica |
| 1 | Abbott Habit, Venice, CA |
| 1 | Westside Tavern after movie 'Boyhood'. |
| 1 | Warehouse |
| 1 | El Charro |
| 1 | Gilly's, Los Gatos (visited Zach, Alize, Kristen, Kyle, Marie, Jim, Soren) |
| 1 | Swingers |
| 1 | Dining room table at home |
| 1 | Carls Jr. |
| 1 | Joe's Crab Shack, Montebello |
| 1 | Solano's Café, La Quinta |
| 1 | Lara's Mexican, Santa Monica |
| 1 | C and O Trattoria, Venice |
| 1 | Baja Cantina (brunch we won at Thursday Night Football) |
| 1 | Home, Dog Food w/Izzy |
| 1 | Counter, MDR |
| 1 | Terrace Café, Marina Del Rey |
| 1 | Waterfront Grill, Santa Monica on Easter Sunday |
| 1 | Watergrill, Santa Monica |
| 1 | The Kettle, Manhattan Beach |
| 1 | Cafe 50s, Venice |
| 1 | The Apricot Tree, Firebaugh, CA |
| 1 | Peets, Oakland, CA |
| 1 | Denny's, Hacienda Heights |
| 1 | Preston Way dining room |
| 1 | 35000 feet above Toronto enroute to Amsterdam |
| 1 | Kira Wira, Serengeti, Tanzenia, Africa |
| 1 | IHOP MDR |
| 1 | Baby Blues BBQ |
| 1 | Yard House, MDR |
| 1 | Venice Cucina on Nancy's 6th AA Bday |
| 1 | Hopdaddy - Playa Vista, CA |
| 1 | Plancha Tacos, Venice - After Gordon's Halloween party. |
| 1 | Casa Linda, Venice |
| 1 | Home - Halloween |
| 1 | Terrace Cafe, MDR |
| 1 | The Anchor, Venice |
| 1 | Jerry's Deli, MDR |
| 1 | Abbots Habit, Abbot Kinney, Venice |
| 1 | Rose Cafe, Venice - reopening |
| 1 | Home - Blue Apron |
| 1 | The Independence, Santa Monica |
| 1 | Superba Bread & Food |
| 1 | Mill Creek Inn, Mentone |
| 1 | Islands, Marina Del Rey |
| 1 | Bob's Big Boy, Calemesa |
| 1 | Dan Tana's |
| 1 | Cairo Cowboy, Venice |
| 1 | Cafe 50's, Venice |
| 1 | Boss's Nova, WLA |
| 1 | Wurstüche, Venice |
| 1 | Taco Bell, Corona |
| 1 | Mercedes |
| 1 | Nichols |
| 1 | Home with Izzy and Paul |
| 1 | Simmzy's |
| 1 | Tommy's, Northridge |
| 1 | Norms, West Covina |
| 1 | La Quinta Baking Co. |
| 1 | Café Vida, Culver City |
| 1 | Maria's Mariscos, Los Angeles |
| 1 | Indian Wells pool |
| 1 | Tender Tenders, Marina Del Rey |
| 1 | Bin 73, MDR |
| 1 | Firestone Walker Brewery, MDR (just opened) |
| 1 | Shophouse, Santa Monica |
| 1 | Trip, Santa Monica w/Mike & Ben |
| 1 | Killer Cafe, Marina Del Rey |
| 1 | Morfia's, Marina Del Rey |
| 1 | Baja Fresh |
| 1 | Casablanca |
| 1 | Burgers and Beer, Santa Monica, CA |
| 1 | Simzy's, Venice |
| 1 | Upper West, WLA on Pico |
| 1 | Pizza Hut, Lake Powell, AZ |
| 1 | George's (Café 50s fire last night!) |
| 1 | Baby Blue's BBQ, Venice |
| 1 | Hal's, Venice |
| 1 | Norm's, WLA |
| 1 | In and Out, Marina Del Rey |
| 1 | Housekeeping Camp, Yosemite |
| 1 | Penmar Golf Course |
| 1 | Non Stop Sushi, Santa Monica |
| 1 | Abredos Fresh Mexican, City of Industry |
| 1 | Spencer's, Palm Springs |
| 1 | Yardhouse, Rancho Mirage |
| 1 | Grill on Main, La Quinta |
| 1 | Big Deans, Santa Monica |
| 1 | Nichols, Marina Del Rey |
| 1 | Westside Tavern, WLA w/Michael & Shannon |
| 1 | Burgers n Brew, Santa Monica |
| 1 | Misfit, Santa Monica |
| 1 | Corky's, Sherman Oaks |
| 1 | Teddy's, West L.A. |
| 1 | Rutt's, Culver City |
| 1 | The Wallace, Culver City |
| 1 | Norms, WLA |
| 1 | Starbucks, Mar Vista |
| 1 | Taco Bell, Mar Vista |
| 1 | Larry's, Venice |
| 1 | The Mar Vista, Mar Vista |
| 1 | Centennial, Venice |
| 1 | Hop Doddy, Playa Vista |
| 1 | Burger Lounge, Culver City |
| 1 | Islands, MDR |
| 1 | Jimmy's Famous American Tavern, Santa Monica |
| 1 | Jacks N Joe, Downtown L.A. |
| 1 | Water grill, Santa Monica |
| 1 | Freddy Smalls Bar and Kitchen, WLA |
| 1 | Bolsa Chica Park + Goose Lake on way home from San Clemente |
| 1 | Duke's, Huntington Beach |
| 1 | Lunetta All Day, WLA |
| 1 | Cava, Venice |
| 1 | Blue Daisy, Santa Monica |
| 1 | Ashland Hill, CA |
| 1 | Candle, Venice |
| 1 | Cole's, Los Angeles |
| 1 | Madonna Inn, San Luis Obisbo, CA |
| 1 | Cracked Egg Cafe, Kernville, CA |
| 1 | Ewings, Kernville, CA |
| 1 | Kernville Saloon, Kernville, CA |
| 1 | Kern River Brewing Co, Kernville, CA - Home of Isabella Blond |
| 1 | Jinya, Santa Monica, CA |
| 1 | On The Beach RV Park, Port Aransas, TX |
| 1 | Rio Grande River, Las Cruces, NM |
| 1 | General Store and Cafe, Hillsburo, CA |
| 1 | Bob’s Big Boy, Calimesa, CA |
| 1 | Novel Cafe, Santa Monica |
| 1 | Licanda Positano, MDR |
| 1 | Village Inn, Balboa Island |
| 1 | Balboa Island, CA |
| 1 | Ruby’s, Newport Pier |
| 1 | Totem Cafe, Lone Pine, CA |
| 1 | Intake frozen lake, Bishop, CA |
| 1 | Twohey’s (last day) |
| 1 | The Shack, Playa Del Rey |
| 1 | Arrowhead, CA |
| 1 | Belgian Waffle House, Lake Arrowhead, CA |
| 1 | The Albright, Santa Monica Pier, CA |
| 1 | Cabo, Santa Monica |
| 1 | Krispy Kreme, Santa Monica |
| 1 | Tom’s Place Cafe, Hwy 395, CA |
| 1 | Thai Dishes on Broadway, Santa Monica, CA |
| 1 | Little Fatty, Mar Vista, CA |
| 1 | Larry’s, Venice |
| 1 | Canter’s, Hollywood |
| 1 | Island’s |
| 1 | The Mar Vista |
| 1 | Market Place Cafe, L.A. (aka The Truck Stop or Potato Cafe) |
| 1 | Wind and Sea, Dana Point Harbor, CA |
| 1 | Doheny State Beach |
| 1 | Mariasol, Santa Monica Pier |
| 1 | Sharkie’s, MDR |
| 1 | Festive Walker, MDR |
| 1 | Home, Perfect - Ed Sheeran |
| 1 | Terrace, MDR |
| 1 | Charcoal, MDR |
| 1 | Baja Cantina, MDR |
| 1 | Hiho, Santa Monica |
| 1 | Diner on Wilshire, SM |
| 1 | Erewon, SM |
| 1 | Meat, SM |
| 1 | George’s, Venice |
| 1 | Fred 62 |
| 1 | Green’s Up |
| 1 | Henri’s, Oxnard |
| 1 | Liquid Room, Culver City |
| 1 | Big Bear |
| 1 | Makani, Venice |
| 1 | Jimmy’s Famous American Tavern, Santa Monica |
| 1 | La Cabańa, Venice |
| 1 | Mes’s Diner, Santa Monica |
| 1 | The Strand House Bar, Manhattan Beach |
| 1 | San Clemente State Beach |
| 1 | The Grand Hotel, Salem, OR |
| 1 | Rincon Parkway |
| 1 | Johnnie Pastrami |
| 1 | Esau’s Cafe, Carpenteria |
| 1 | Taco Bell, Fontana |
| 1 | Frontier Cafe, Landers/Yucca Valley |
| 1 | Boso Nova, West Los Angeles |
| 1 | Burgers and Brew, Venice |
| 1 | Victorian, Santa Monica |
| 1 | Starks MDR |
| 1 | Shoops, Santa Monica |
| 1 | Gnarbox |
| 1 | Clutch |
| 1 | Johnnie’s Pastrami |
| 1 | George’s |
| 1 | Barone’s |
| 1 | Mel’s, Santa Monica |
| 1 | Superba, Venice |
| 1 | Venice Beach Bar and Kitchen |
| 1 | Amigo’s, Pasadena |
| 1 | Gulp, Playa Vista |
| 1 | George’s, Santa Monica |
| 1 | Foxy’s, Glendale |
| 1 | Bonita Ranch, Lytle Creek, CA |
| 1 | American Beauty, Venice |
| 1 | Campland, San Diego, Nancy’s birthday and Parrot Head |
| 1 | Campland in the RV |
| 1 | Perry’s Beach Cafe, Santa Monica |
| 1 | Kaiser — Metatarsal fracture, ankle sprain, and proximal phalange dislocation |
| 1 | Gloria’s |
| 1 | San Clemente |
| 1 | Fisherman’s Restaurant and Bar, San Clemente Pier |
| 1 | Tender Greens, MDR - Goodbye Louie 💙 |
| 1 | RJ’s Cafe Dana Point |
| 1 | Ingo’s, Santa Monica |
| 1 | Atmosphere, Culver City |
| 1 | Johnney’s Pastrami |
| 1 | Mexico City |
| 1 | La Posada Hotel Bar, La Paz, Baja California, Sur |
| 1 | 33rd St Bistro, Sacramento |
| 1 | Shoops |
| 1 | Spitfire |
| 1 | The Pier House, Venice |
| 1 | Big John's, Wrightwood |
| 1 | Camp Scheideck Lodge, Reyes Creek |
| 1 | Agave Maria's, Ojai |
| 1 | Mercado, Santa Monica |
| 1 | Spitfire, Santa Monica - Closing day |
| 1 | Tahoe Valley Campground #147 - Calrisian |
| 1 | Home - Quarantine Day 6 |
| 1 | Home - Quarantine Day 7 |
| 1 | Home - Quarantine Day 10 |
| 1 | Home - back yard |
| 1 | Home - diving board |
| 1 | Home -patio |
| 1 | Home - living room |
| 1 | Tahoe - Sonora Pass |
| 1 | Kingsburg RV Resort on the Kings River |
| 1 | Bakersfield |
| 1 | Home - front yard |
| 1 | Caterina's, San Clemente |
| 1 | San Mateo Campground |
| 1 | Founder's Park, Ladera Ranch, CA |
| 1 | Lake Ellery |
| 1 | Crestview Rest Area |
| 1 | Bridgeport Resevoir |
| 1 | Red Rock Canyon |
| 1 | Home - kitchen (thinking of J Nichol's) |
| 1 | Coso Junction Rest Stop, 395 |
| 1 | Amargosa River, NV |
| 1 | Takopa Hot Springs |
| 1 | Tuscan Springs Hotel and Spa, Desert Hot Springs, CA |
| 1 | Johnson Valley |
| 1 | Whittier Narrows Recreation Area |
| 1 | Padero Beach Grill, Carpinteria |
| 1 | Delgados, Carpenteria |
| 1 | Calico - Mule Canyon Road |
| 1 | Calico - Mule Canyon Road 9:9 |
| 1 | The Penmar |
| 1 | Duke's Huntington Beach |
| 1 | Watergrill, SM |
| 1 | Denver Meadows RV Park |
| 1 | Craig, CO |
| 1 | Palm Desert |
| 1 | House of Pies, Hollywood |
| 1 | Hi Jolly BLM Campground, AZ |
| 1 | Verde Ranch, Park Verde, AZ |
| 1 | Cinder Hills (OHV) Flagstaff, AZ |
| 1 | Navaholand Resort, Tuba City, AZ |
| 1 | Goulding's Tesort and RV |
| 1 | Doc Martens, Taos, NM |
| 1 | Bent Street Deli & Café, Taos, NM |
| 1 | Tomasito's, Santa Fe, NM |
| 1 | Plaza Cafe, Santa Fe, NM |
| 1 | French's Park, Santa Fe, NM |
| 1 | Dolina Cafe & Bakery, Santa Fe, NM |
| 1 | Ranch House, Santa Fe, NM |
| 1 | Cow Girl, Santa Fe, NM |
| 1 | Lincoln County, NM |
| 1 | Oswald Vineyard, Brownfield, TX |
| 1 | Rosewell, NM |
| 1 | Outrigger Tavern, San Clemente, CA |
| 1 | Hat, Lake Forest, CA |
| 1 | San Clemente, CA |
| 1 | Yardhouse, MDR |
| 1 | Neptunes Net, Malibu |
| 1 | Denny's, Grapevine, CA |
| 1 | Lake Baron |
| 1 | Jawbone Canyon, CA |
| 1 | Sgt. Steve Owen Memorial Park, Lancaster, CA |
| 1 | Little Branch Cafe, Chicago |
| 1 | Beat Kitchen, Chicago River Walk |
| 1 | Berghoff's, Chicago |
| 1 | Aroma Coffee and Wine Bar, Crystal Lake, IL |
| 1 | Benedict's La Strava, IL |
| 1 | Antioch Pizza Shop, Woodstock, IL |
| 1 | Dear John's, Culver City |
| 1 | Norms, West Hollywood |
| 1 | Twoheys |
| 1 | Fromins, Santa Monica |
| 1 | Clearman's Galley, The Boat, Rosemead, CA |
| 1 | Taverna, Mar Vista |
| 1 | Maple Block, Culver City |
| 1 | Casablanca, Venice |
| 1 | Campland by the Bay, San Diego |
| 1 | Morro Bay State Beach |
| 1 | Swingers, Hollywood |
| 1 | Surfside Seafood, Hueneme |
| 1 | In-n-Out, Westwood |
| 1 | Busy Bee Diner, Ventura |
| 1 | Olancha Cafe, Okancha, CA |
| 1 | Lakeshore, Tahoe |
| 1 | Woods Lake, Kirkwood, CA |
| 1 | Pickled Porch, Angles Camp, CA |
| 1 | Bear Mountain Pizza, Sequoia |
| 1 | Our Place Café, Woodlake, CA |
| 1 | Clearman's Northwoods inn, Santa Ana |
| 1 | Vons, Goleta - RV Breakdown |
| 1 | Space Age Cafe, AZ |
| 1 | Hanger 6, Uvalde, TX |
| 1 | Bikini Joe's, El Paso, TX |
| 1 | Julio's, El Paso, TX |
| 1 | Adobe Cantina, Akela, NM |
| 1 | El Torito, MDR |
| 1 | Mao's, Venice |
| 1 | Gjusta, Venice |
| 1 | Zuma Beach, Malibu, CA |
| 1 | In-N-Out, Ontario, CA |
| 1 | John O'Groats |
| 1 | Nate & Al's |
| 1 | Home, Onyx Patio |
| 1 | La Casita, Palm Desert |
| 1 | Ihop, LAX |
| 1 | The Six Chow House, WLA |
| 1 | Gonzo's, Yreka |
| 1 | Vancouver Farmers Market, WA |
| 1 | Oxnard |
| 1 | Botegga Louie |
| 1 | Micelli's, Hollywood |
| 1 | PCH, Malibu |
| 1 | Sugar & Spice, Santa Fe Springs |
| 1 | Arth, Culver City |
| 1 | Belles, Venice |
| 1 | Denny's, Cerritos |
| 1 | Tacos Tamix, Pacific Ave, Venice |
| 1 | Vito's |
| 1 | Harris Ranch steakhouse, Cailinga￼ |
| 1 | Harris Ranch, Cailinga￼ |
| 1 | Dill's Deli, Redding |
| 1 | Rogue Valley State Park, OR |
| 1 | Burly County Park , OR |
| 1 | Pirates Cove, Bar View, OR |
| 1 | Ilwaco, WA |
| 1 | Old Town Cafe, Ilwaco, WA |
| 1 | Grayland Beach State Park, WA |
| 1 | Billy's Bar and Grill, Aberdeen, WA |
| 1 | Kalaloch, WA |
| 1 | By the Bsy Cafe, Sekiu, WA |
| 1 | Sol Duc Campground, WA |
| 1 | Port Angeles Ferry Terminal, WA |
| 1 | Port Angeles, WA |
| 1 | Port Angeles, WA - Victoria, BC Ferry |
| 1 | Butchart Gardens, BC |
| 1 | St. Elizabeth, Sydney, BC |
| 1 | Malahat, BC |
| 1 | Bridgeman Bistro, Mill Bay, BC |
| 1 | Beehive Campground, Mill Bay, BC |
| 1 | Nanaimo, BC |
| 1 | Thetis Island, BC |
| 1 | Trees, Parksville |
| 1 | Victoria /Port Angeles Ferry |
| 1 | Traylor's, Port Angeles, WA |
| 1 | Triton Cove State Park, WA |
| 1 | Olympia, WA |
| 1 | Aurora, OR |
| 1 | Susanville |
| 1 | Lodi |
| 1 | Costco, Fresno |
| 1 | Pixley, CA |
| 1 | Roscoe's Chicken & Waffles |
| 1 | Layla's |
| 1 | Panda Express, MDR |
| 1 | Mañana Café, Venice |
| 1 | Home backyard |
| 1 | Rockos, Culver City |
| 1 | Mañana Cafe, Culver City |
| 1 | Old Mill Café, Modesto ￼ |
| 1 | Harris Ranch, Coalinga |
| 1 | Simple Simon, Riverside￼ |
| 1 | Olive Ave Mkt, Redlands |
| 1 | Barn, Koreatown |
| 1 | Rutt's |
| 1 | Yardhouse |
| 1 | Carpinteria State Beach |
| 1 | Island Brewery, Carpinteria |
| 1 | Portos, West Covina |
| 1 | Mario's, Bermuda Dunes |
| 1 | Red Ocotillo, Borrego Springs |
| 1 | Propeller, Borrego Springs ￼ |
| 1 | Sally's |
| 1 | Keedy's |
| 1 | Papille Gustive, Santa Monica |
| 1 | Dakota |
| 1 | Dakota - Patio |
| 1 | LG's Steakhouse |
| 1 | Ggiata Deli, Venice |
| 1 | Mendocino Farms, MDR ￼ |
| 1 | Mar Vista Market |
| 1 | Shoop's, Santa Monica |
| 1 | Paris Baguette, West Covina |
| 1 | Hideout, Palm Desert |
| 1 | Clark Street Diner |
| 1 | The Boy and the Bear, Culver City |
| 1 | Simpang Asia Indonesian |
| 1 | In-N-Out |
| 1 | Tartine, Santa Monica |
| 1 | Bottega Louie |
| 1 | Corktree, Carpinteria |
| 1 | Brent's, Westlake Village |
| 1 | Electric Bleu |
| 1 | Gjelina |
| 1 | Bluey's |
| 1 | Checker Hall, Highland Hall, Highland Park |
| 1 | Huntington Beach, CA |
| 1 | Ola Mexican Kitchen, HB |
| 1 | Nelson's, Terrina, Palos Verdes |
| 1 | Carpinteria #365 |
| 1 | East Coast Bagel |
| 1 | The Lunch Spot, Palm Desert |
| 1 | Maple Block |
| 1 | Hof's Hut, Long Beach |
| 1 | Mañana, Culver City |
| 1 | Millcross, Culver City |
| 1 | Saguaro Cafe |
| 1 | Metro Cafe, Culver City |
| 1 | Penny's, West Covina |
| 1 | McDonald's, Calimesa |
| 1 | Breakaway Cafe, Culver City |
| 1 | Rae's, Santa Monica |
| 1 | Cafe Belen |
| 1 | Surpuba Bread and Food |
| 1 | The Mill, Murietta |
| 1 | Ba Ba Loo, Palm Desert |
| 1 | BNP Paribas |
| 1 | Cliffhouse, La Quinta |
| 1 | Black Bear Diner, Colton |
| 1 | Noah's Bagels, MDR |
| 1 | Hamburger Habit |
| 1 | Venice Beach Club, @Rose |
| 1 | Flake, Venice |
| 1 | Pasta Sisters, Culver City |
| 1 | Centinella Café, Culver City |
| 1 | Brass Bird Cafe, Carpinteria |
| 1 | Palisades Lutheran Church |
| 1 | Bike Shed Moto Co, DTLA |
| 1 | Palm Cafe, La Quinta |
| 1 | Beethoven Market |
| 1 | Hopdoddy, Playa del Rey |
| 1 | The Cloverfield |
| 1 | Sauced, Redondo Beach |
| 1 | Bread Basket, Tustin |
| 1 | Keedy's, La Quinta |
| 1 | Broken Spanish |
| 1 | Leo Carrillo |
| 1 | Lutheran Church of the Palisades |
| 1 | Nancy's prediction on March 2, 2015 |

### `data/seeds/dominos/dominos_seed_2026-06-16.xlsx`

1400 Where cells, 583 distinct.

| Count | Name |
|------:|------|
| 303 | Home - Island |
| 78 | Home - dining room |
| 68 | Zinque, Venice |
| 51 | Home |
| 33 | Home - kitchen |
| 33 | Home - Patio |
| 25 | Cafe 50's |
| 20 | Home - pad patio |
| 15 | Home - diving board table |
| 12 | Home - RV |
| 11 | George's |
| 11 | Home - patio |
| 10 | Dakota Trail |
| 9 | Café 50s |
| 7 | IHOP, MDR |
| 7 | George's, Santa Monica |
| 7 | J Nichols |
| 6 | Centanni |
| 6 | Café 50's, Venice |
| 5 | Café 50s, Venice |
| 5 | George's, Venice |
| 5 | Maxine's |
| 5 | Campground by the Lake, Tahoe |
| 4 | Superba Bread & Food, Venice |
| 4 | Bob's Big Boy, Calimesa |
| 4 | Café 50's |
| 4 | La Cabaña |
| 4 | Westside Tavern, WLA |
| 4 | La Cabaña, Venice |
| 4 | Hal Burns Truck, Santa Fe, NM |
| 3 | Swingers, Santa Monica |
| 3 | Westside Tavern |
| 3 | J. Nichols, MDR |
| 3 | Clutch, Venice |
| 3 | George's Burgers |
| 3 | Swinger's, Santa Monica |
| 3 | Sidewalk Cafe, Venice |
| 3 | Tahoe Valley Campground |
| 3 | Jawbone |
| 3 | Sunset Vista Campground, Huntington Beach |
| 3 | Johnnie's Pastrami |
| 3 | Home, Patio |
| 3 | The Spot, Carpinteria |
| 2 | Cafe 50's, Venice |
| 2 | Swingers |
| 2 | Watergrill, Santa Monica |
| 2 | IHOP, Marina Del Rey |
| 2 | J Nichols, MDR |
| 2 | Bossa Nova, WLA |
| 2 | Pann's |
| 2 | Centanni, Venice |
| 2 | Killer Shrimp Cafe, MDR |
| 2 | Ruth's Chris, MDR |
| 2 | Cafe 50s |
| 2 | Izzy's Deli, Santa Monica |
| 2 | Rustic Kitchen |
| 2 | Le Pain Quotidien |
| 2 | La Cabana, Venice |
| 2 | Busy Bee, Ventura |
| 2 | Killer Cafe, MDR |
| 2 | Perry’s, Santa Monica |
| 2 | Shoop’s, Santa Monica |
| 2 | Dinah’s |
| 2 | Superba Bread and Food, Venice |
| 2 | Port Hueneme |
| 2 | Johnny’s Pastrami |
| 2 | San Clemente St Beach |
| 2 | Steamers |
| 2 | Home - Landau |
| 2 | Tahoe - Steamers |
| 2 | South Lake Tahoe, 4th St |
| 2 | Carpenteria State Beach #106 |
| 2 | Carpinteria State Beach #357 |
| 2 | Home, Kitchen |
| 2 | Mel's Diner, Santa Monica |
| 2 | Gold Sands Casino RV Park, Carson City, NV |
| 2 | Bishop, CA |
| 2 | Moose Lodge, SLT |
| 2 | Home - Dining room |
| 2 | Ihop, MDR |
| 2 | Blueys |
| 2 | Faria State Park #18, Ventura |
| 2 | Corky's, Fontana |
| 2 | Clearman's North Woods Inn, La Mirada ￼ |
| 2 | Saby's |
| 2 | Penmar |
| 2 | Companion, Venice |
| 2 | Tapiola Park, Asteria, OR |
| 2 | Mora Campground, La Puch, WA |
| 2 | Victoria, BC |
| 2 | Ladysmith, BC |
| 2 | Teddy's Diner |
| 2 | Dinah's |
| 2 | iHop, Sepulveda, Culver City |
| 2 | The Manchester |
| 2 | Esau's, Carpinteria |
| 2 | Elysee Bakery and Café, Westwood |
| 2 | Rockinwagner |
| 2 | iHop, MDR |
| 2 | Tacos Por Favor |
| 2 | The Penmar, Venice |
| 2 | Urban Plates |
| 2 | Malibu |
| 2 | Newport Dunes RV Park |
| 1 | Home Kitchen |
| 1 | Spitfire, Santa Monica |
| 1 | On Montana |
| 1 | Backyard |
| 1 | Meet me in Paris, Culver City |
| 1 | Bob's Big Boy, L.A. on Wilshire |
| 1 | Upper West |
| 1 | Wurshkuke, Venice |
| 1 | Backyard, Venice |
| 1 | 101 Cafe, Hollywood |
| 1 | Solerno beach |
| 1 | Abbot's Habit |
| 1 | Engine Co. 28 |
| 1 | Abbott's Habit |
| 1 | Maxwells |
| 1 | Pitfire |
| 1 | Literati cafe |
| 1 | Rick's Tavern, Santa Monica |
| 1 | Café 50s, Venice, California |
| 1 | Venice Bistro, Venice, CA |
| 1 | Abbott Habit, Venice, CA |
| 1 | Westside Tavern after movie 'Boyhood'. |
| 1 | Warehouse |
| 1 | El Charro |
| 1 | Gilly's, Los Gatos (visited Zach, Alize, Kristen, Kyle, Marie, Jim, Soren) |
| 1 | jnicohls |
| 1 | Dining room table at home |
| 1 | Carl's Jr. Sepulveda and Venice |
| 1 | Joe's Crab Shack, Montebello |
| 1 | Solano's Café, La Quinta |
| 1 | Lara's Mexican, Santa Monica |
| 1 | Clutch, Venice (six days after opening) |
| 1 | C and O Trattoria, Venice |
| 1 | Baja Cantina (brunch we won at Thursday Night Football) |
| 1 | Home, Dog Food w/Izzy |
| 1 | Counter, MDR |
| 1 | Terrace Café, Marina Del Rey |
| 1 | Waterfront Grill, Santa Monica on Easter Sunday |
| 1 | The Kettle, Manhattan Beach |
| 1 | Lost On Hwy 111, Palm Desert |
| 1 | Cafe 50s, Venice |
| 1 | The Apricot Tree, Firebaugh, CA |
| 1 | Peets, Oakland, CA |
| 1 | Denny's, Hacienda Heights |
| 1 | Preston Way dining room |
| 1 | 35000 feet above Toronto enroute to Amsterdam |
| 1 | Kira Wira, Serengeti, Tanzenia, Africa |
| 1 | IHOP MDR |
| 1 | Baby Blues BBQ |
| 1 | Yard House, MDR |
| 1 | Venice Cucina on Nancy's 6th AA Bday |
| 1 | Hopdaddy - Playa Vista, CA |
| 1 | Plancha Tacos, Venice - After Gordon's Halloween party. |
| 1 | Casa Linda, Venice |
| 1 | Home - Halloween |
| 1 | Terrace Cafe, MDR |
| 1 | The Anchor, Venice |
| 1 | Jerry's Deli, MDR |
| 1 | Abbots Habit, Abbot Kinney, Venice |
| 1 | Rose Cafe, Venice - reopening |
| 1 | Home - Blue Apron |
| 1 | The Independence, Santa Monica |
| 1 | Superba Bread & Food |
| 1 | Mill Creek Inn, Mentone |
| 1 | Islands, Marina Del Rey |
| 1 | Bob's Big Boy, Calemesa |
| 1 | Dan Tana's |
| 1 | Cairo Cowboy, Venice |
| 1 | Boss's Nova, WLA |
| 1 | Wurstüche, Venice |
| 1 | Taco Bell, Corona |
| 1 | Mercedes |
| 1 | Nichols |
| 1 | Home with Izzy and Paul |
| 1 | Simmzy's |
| 1 | Tommy's, Northridge |
| 1 | Norms, West Covina |
| 1 | La Quinta Baking Co. |
| 1 | Café Vida, Culver City |
| 1 | Maria's Mariscos, Los Angeles |
| 1 | Indian Wells pool |
| 1 | Tender Tenders, Marina Del Rey |
| 1 | Bin 73, MDR |
| 1 | Firestone Walker Brewery, MDR (just opened) |
| 1 | Shophouse, Santa Monica |
| 1 | Trip, Santa Monica w/Mike & Ben |
| 1 | Killer Cafe, Marina Del Rey |
| 1 | Morfia's, Marina Del Rey |
| 1 | Baja Fresh |
| 1 | Casablanca |
| 1 | Burgers and Beer, Santa Monica, CA |
| 1 | Simzy's, Venice |
| 1 | Upper West, WLA on Pico |
| 1 | Pizza Hut, Lake Powell, AZ |
| 1 | George's (Café 50s fire last night!) |
| 1 | Baby Blue's BBQ, Venice |
| 1 | Hal's, Venice |
| 1 | Norm's, WLA |
| 1 | In and Out, Marina Del Rey |
| 1 | Housekeeping Camp, Yosemite |
| 1 | Penmar Golf Course |
| 1 | Non Stop Sushi, Santa Monica |
| 1 | Abredos Fresh Mexican, City of Industry |
| 1 | Spencer's, Palm Springs |
| 1 | Yardhouse, Rancho Mirage |
| 1 | Grill on Main, La Quinta |
| 1 | Big Deans, Santa Monica |
| 1 | Nichols, Marina Del Rey |
| 1 | Westside Tavern, WLA w/Michael & Shannon |
| 1 | Burgers n Brew, Santa Monica |
| 1 | Misfit, Santa Monica |
| 1 | Corky's, Sherman Oaks |
| 1 | Teddy's, West L.A. |
| 1 | Rutt's, Culver City |
| 1 | The Wallace, Culver City |
| 1 | Norms, WLA |
| 1 | Starbucks, Mar Vista |
| 1 | Taco Bell, Mar Vista |
| 1 | Larry's, Venice |
| 1 | The Mar Vista, Mar Vista |
| 1 | Centennial, Venice |
| 1 | Hop Doddy, Playa Vista |
| 1 | Burger Lounge, Culver City |
| 1 | Islands, MDR |
| 1 | Jimmy's Famous American Tavern, Santa Monica |
| 1 | Jacks N Joe, Downtown L.A. |
| 1 | Water grill, Santa Monica |
| 1 | Freddy Smalls Bar and Kitchen, WLA |
| 1 | Bolsa Chica Park + Goose Lake on way home from San Clemente |
| 1 | Duke's, Huntington Beach |
| 1 | Lunetta All Day, WLA |
| 1 | Cava, Venice |
| 1 | Blue Daisy, Santa Monica |
| 1 | Ashland Hill, CA |
| 1 | Candle, Venice |
| 1 | Cole's, Los Angeles |
| 1 | Madonna Inn, San Luis Obisbo, CA |
| 1 | Cracked Egg Cafe, Kernville, CA |
| 1 | Ewings, Kernville, CA |
| 1 | Kernville Saloon, Kernville, CA |
| 1 | Kern River Brewing Co, Kernville, CA - Home of Isabella Blond |
| 1 | Jinya, Santa Monica, CA |
| 1 | On The Beach RV Park, Port Aransas, TX |
| 1 | Rio Grande River, Las Cruces, NM |
| 1 | General Store and Cafe, Hillsburo, CA |
| 1 | Bob’s Big Boy, Calimesa, CA |
| 1 | Novel Cafe, Santa Monica |
| 1 | Licanda Positano, MDR |
| 1 | Village Inn, Balboa Island |
| 1 | Balboa Island, CA |
| 1 | Ruby’s, Newport Pier |
| 1 | Totem Cafe, Lone Pine, CA |
| 1 | Intake frozen lake, Bishop, CA |
| 1 | Twohey’s (last day) |
| 1 | The Shack, Playa Del Rey |
| 1 | Arrowhead, CA |
| 1 | Belgian Waffle House, Lake Arrowhead, CA |
| 1 | The Albright, Santa Monica Pier, CA |
| 1 | Cabo, Santa Monica |
| 1 | Krispy Kreme, Santa Monica |
| 1 | Tom’s Place Cafe, Hwy 395, CA |
| 1 | Thai Dishes on Broadway, Santa Monica, CA |
| 1 | Little Fatty, Mar Vista, CA |
| 1 | Larry’s, Venice |
| 1 | Canter’s, Hollywood |
| 1 | Island’s |
| 1 | The Mar Vista |
| 1 | Market Place Cafe, L.A. (aka The Truck Stop or Potato Cafe) |
| 1 | Wind and Sea, Dana Point Harbor, CA |
| 1 | Doheny State Beach |
| 1 | Mariasol, Santa Monica Pier |
| 1 | Sharkie’s, MDR |
| 1 | Festive Walker, MDR |
| 1 | Home, Perfect - Ed Sheeran |
| 1 | Terrace, MDR |
| 1 | Charcoal, MDR |
| 1 | Baja Cantina, MDR |
| 1 | Hiho, Santa Monica |
| 1 | Diner on Wilshire, SM |
| 1 | Erewon, SM |
| 1 | Meat, SM |
| 1 | George’s, Venice |
| 1 | Fred 62 |
| 1 | Green’s Up |
| 1 | Henri’s, Oxnard |
| 1 | Liquid Room, Culver City |
| 1 | Big Bear |
| 1 | Makani, Venice |
| 1 | Jimmy’s Famous American Tavern, Santa Monica |
| 1 | La Cabańa, Venice |
| 1 | Mes’s Diner, Santa Monica |
| 1 | The Strand House Bar, Manhattan Beach |
| 1 | San Clemente State Beach |
| 1 | The Grand Hotel, Salem, OR |
| 1 | Rincon Parkway |
| 1 | Johnnie Pastrami |
| 1 | Esau’s Cafe, Carpenteria |
| 1 | Taco Bell, Fontana |
| 1 | Frontier Cafe, Landers/Yucca Valley |
| 1 | Boso Nova, West Los Angeles |
| 1 | Burgers and Brew, Venice |
| 1 | Victorian, Santa Monica |
| 1 | Starks MDR |
| 1 | Shoops, Santa Monica |
| 1 | Gnarbox |
| 1 | Clutch |
| 1 | Johnnie’s Pastrami |
| 1 | George’s |
| 1 | Barone’s |
| 1 | Mel’s, Santa Monica |
| 1 | Superba, Venice |
| 1 | Venice Beach Bar and Kitchen |
| 1 | Amigo’s, Pasadena |
| 1 | Gulp, Playa Vista |
| 1 | George’s, Santa Monica |
| 1 | Foxy’s, Glendale |
| 1 | Bonita Ranch, Lytle Creek, CA |
| 1 | American Beauty, Venice |
| 1 | Campland, San Diego, Nancy’s birthday and Parrot Head |
| 1 | Campland in the RV |
| 1 | Perry’s Beach Cafe, Santa Monica |
| 1 | Kaiser — Metatarsal fracture, ankle sprain, and proximal phalange dislocation |
| 1 | Gloria’s |
| 1 | San Clemente |
| 1 | Fisherman’s Restaurant and Bar, San Clemente Pier |
| 1 | Tender Greens, MDR - Goodbye Louie 💙 |
| 1 | RJ’s Cafe Dana Point |
| 1 | Ingo’s, Santa Monica |
| 1 | Atmosphere, Culver City |
| 1 | Johnney’s Pastrami |
| 1 | Mexico City |
| 1 | La Posada Hotel Bar, La Paz, Baja California, Sur |
| 1 | 33rd St Bistro, Sacramento |
| 1 | Shoops |
| 1 | Spitfire |
| 1 | The Pier House, Venice |
| 1 | Big John's, Wrightwood |
| 1 | Camp Scheideck Lodge, Reyes Creek |
| 1 | Agave Maria's, Ojai |
| 1 | Mercado, Santa Monica |
| 1 | Spitfire, Santa Monica - Closing day |
| 1 | Tahoe Valley Campground #147 - Calrisian |
| 1 | Home - Quarantine Day 6 |
| 1 | Home - Quarantine Day 7 |
| 1 | Home - Quarantine Day 10 |
| 1 | Home - back yard |
| 1 | Home - diving board |
| 1 | Home -patio |
| 1 | Home - living room |
| 1 | Tahoe - Sonora Pass |
| 1 | Kingsburg RV Resort on the Kings River |
| 1 | Bakersfield |
| 1 | Home - front yard |
| 1 | Caterina's, San Clemente |
| 1 | San Mateo Campground |
| 1 | Founder's Park, Ladera Ranch, CA |
| 1 | Lake Ellery |
| 1 | Crestview Rest Area |
| 1 | Bridgeport Resevoir |
| 1 | Red Rock Canyon |
| 1 | Home - kitchen (thinking of J Nichol's) |
| 1 | Coso Junction Rest Stop, 395 |
| 1 | Amargosa River, NV |
| 1 | Takopa Hot Springs |
| 1 | Tuscan Springs Hotel and Spa, Desert Hot Springs, CA |
| 1 | Johnson Valley |
| 1 | Whittier Narrows Recreation Area |
| 1 | Padero Beach Grill, Carpinteria |
| 1 | Delgados, Carpenteria |
| 1 | Calico - Mule Canyon Road |
| 1 | Calico - Mule Canyon Road 9:9 |
| 1 | The Penmar |
| 1 | Duke's Huntington Beach |
| 1 | Watergrill, SM |
| 1 | Denver Meadows RV Park |
| 1 | Craig, CO |
| 1 | Palm Desert |
| 1 | House of Pies, Hollywood |
| 1 | Hi Jolly BLM Campground, AZ |
| 1 | Verde Ranch, Park Verde, AZ |
| 1 | Cinder Hills (OHV) Flagstaff, AZ |
| 1 | Navaholand Resort, Tuba City, AZ |
| 1 | Goulding's Tesort and RV |
| 1 | Doc Martens, Taos, NM |
| 1 | Bent Street Deli & Café, Taos, NM |
| 1 | Tomasito's, Santa Fe, NM |
| 1 | Plaza Cafe, Santa Fe, NM |
| 1 | French's Park, Santa Fe, NM |
| 1 | Dolina Cafe & Bakery, Santa Fe, NM |
| 1 | Ranch House, Santa Fe, NM |
| 1 | Cow Girl, Santa Fe, NM |
| 1 | Lincoln County, NM |
| 1 | Oswald Vineyard, Brownfield, TX |
| 1 | Rosewell, NM |
| 1 | Outrigger Tavern, San Clemente, CA |
| 1 | Hat, Lake Forest, CA |
| 1 | San Clemente, CA |
| 1 | Yardhouse, MDR |
| 1 | Neptunes Net, Malibu |
| 1 | Denny's, Grapevine, CA |
| 1 | Lake Baron |
| 1 | Jawbone Canyon, CA |
| 1 | Sgt. Steve Owen Memorial Park, Lancaster, CA |
| 1 | Little Branch Cafe, Chicago |
| 1 | Beat Kitchen, Chicago River Walk |
| 1 | Berghoff's, Chicago |
| 1 | Aroma Coffee and Wine Bar, Crystal Lake, IL |
| 1 | Benedict's La Strava, IL |
| 1 | Antioch Pizza Shop, Woodstock, IL |
| 1 | Dear John's, Culver City |
| 1 | Norms, West Hollywood |
| 1 | Twoheys |
| 1 | Fromins, Santa Monica |
| 1 | Clearman's Galley, The Boat, Rosemead, CA |
| 1 | Taverna, Mar Vista |
| 1 | Maple Block, Culver City |
| 1 | Casablanca, Venice |
| 1 | Campland by the Bay, San Diego |
| 1 | Morro Bay State Beach |
| 1 | Swingers, Hollywood |
| 1 | Surfside Seafood, Hueneme |
| 1 | In-n-Out, Westwood |
| 1 | Busy Bee Diner, Ventura |
| 1 | Olancha Cafe, Okancha, CA |
| 1 | Lakeshore, Tahoe |
| 1 | Woods Lake, Kirkwood, CA |
| 1 | Pickled Porch, Angles Camp, CA |
| 1 | Bear Mountain Pizza, Sequoia |
| 1 | Our Place Café, Woodlake, CA |
| 1 | Clearman's Northwoods inn, Santa Ana |
| 1 | Vons, Goleta - RV Breakdown |
| 1 | Space Age Cafe, AZ |
| 1 | Hanger 6, Uvalde, TX |
| 1 | Bikini Joe's, El Paso, TX |
| 1 | Julio's, El Paso, TX |
| 1 | Adobe Cantina, Akela, NM |
| 1 | El Torito, MDR |
| 1 | Mao's, Venice |
| 1 | Gjusta, Venice |
| 1 | Zuma Beach, Malibu, CA |
| 1 | In-N-Out, Ontario, CA |
| 1 | John O'Groats |
| 1 | Nate & Al's |
| 1 | Home, Onyx Patio |
| 1 | La Casita, Palm Desert |
| 1 | Ihop, LAX |
| 1 | The Six Chow House, WLA |
| 1 | Gonzo's, Yreka |
| 1 | Vancouver Farmers Market, WA |
| 1 | Oxnard |
| 1 | Botegga Louie |
| 1 | Micelli's, Hollywood |
| 1 | PCH, Malibu |
| 1 | Sugar & Spice, Santa Fe Springs |
| 1 | Arth, Culver City |
| 1 | Belles, Venice |
| 1 | Denny's, Cerritos |
| 1 | Tacos Tamix, Pacific Ave, Venice |
| 1 | Vito's |
| 1 | Harris Ranch steakhouse, Cailinga￼ |
| 1 | Harris Ranch, Cailinga￼ |
| 1 | Dill's Deli, Redding |
| 1 | Rogue Valley State Park, OR |
| 1 | Burly County Park , OR |
| 1 | Pirates Cove, Bar View, OR |
| 1 | Ilwaco, WA |
| 1 | Old Town Cafe, Ilwaco, WA |
| 1 | Grayland Beach State Park, WA |
| 1 | Billy's Bar and Grill, Aberdeen, WA |
| 1 | Kalaloch, WA |
| 1 | By the Bsy Cafe, Sekiu, WA |
| 1 | Sol Duc Campground, WA |
| 1 | Port Angeles Ferry Terminal, WA |
| 1 | Port Angeles, WA |
| 1 | Port Angeles, WA - Victoria, BC Ferry |
| 1 | Butchart Gardens, BC |
| 1 | St. Elizabeth, Sydney, BC |
| 1 | Malahat, BC |
| 1 | Bridgeman Bistro, Mill Bay, BC |
| 1 | Beehive Campground, Mill Bay, BC |
| 1 | Nanaimo, BC |
| 1 | Thetis Island, BC |
| 1 | Trees, Parksville |
| 1 | Victoria /Port Angeles Ferry |
| 1 | Traylor's, Port Angeles, WA |
| 1 | Triton Cove State Park, WA |
| 1 | Olympia, WA |
| 1 | Aurora, OR |
| 1 | Susanville |
| 1 | Lodi |
| 1 | Costco, Fresno |
| 1 | Pixley, CA |
| 1 | Roscoe's Chicken & Waffles |
| 1 | Layla's |
| 1 | Panda Express, MDR |
| 1 | Mañana Café, Venice |
| 1 | Home backyard |
| 1 | Rockos, Culver City |
| 1 | Mañana Cafe, Culver City |
| 1 | Old Mill Café, Modesto ￼ |
| 1 | Harris Ranch, Coalinga |
| 1 | Simple Simon, Riverside￼ |
| 1 | Olive Ave Mkt, Redlands |
| 1 | Barn, Koreatown |
| 1 | Rutt's |
| 1 | Yardhouse |
| 1 | Carpinteria State Beach |
| 1 | Island Brewery, Carpinteria |
| 1 | Portos, West Covina |
| 1 | Mario's, Bermuda Dunes |
| 1 | Red Ocotillo, Borrego Springs |
| 1 | Propeller, Borrego Springs ￼ |
| 1 | Sally's |
| 1 | Keedy's |
| 1 | Papille Gustive, Santa Monica |
| 1 | Dakota |
| 1 | Dakota - Patio |
| 1 | LG's Steakhouse |
| 1 | Ggiata Deli, Venice |
| 1 | Mendocino Farms, MDR ￼ |
| 1 | Mar Vista Market |
| 1 | Shoop's, Santa Monica |
| 1 | Paris Baguette, West Covina |
| 1 | Hideout, Palm Desert |
| 1 | Clark Street Diner |
| 1 | The Boy and the Bear, Culver City |
| 1 | Simpang Asia Indonesian |
| 1 | In-N-Out |
| 1 | Tartine, Santa Monica |
| 1 | Bottega Louie |
| 1 | Corktree, Carpinteria |
| 1 | Brent's, Westlake Village |
| 1 | Electric Bleu |
| 1 | Gjelina |
| 1 | Bluey's |
| 1 | Checker Hall, Highland Hall, Highland Park |
| 1 | Huntington Beach, CA |
| 1 | Ola Mexican Kitchen, HB |
| 1 | Nelson's, Terrina, Palos Verdes |
| 1 | Carpinteria #365 |
| 1 | East Coast Bagel |
| 1 | The Lunch Spot, Palm Desert |
| 1 | Maple Block |
| 1 | Hof's Hut, Long Beach |
| 1 | Mañana, Culver City |
| 1 | Millcross, Culver City |
| 1 | Saguaro Cafe |
| 1 | Metro Cafe, Culver City |
| 1 | Penny's, West Covina |
| 1 | McDonald's, Calimesa |
| 1 | Breakaway Cafe, Culver City |
| 1 | Rae's, Santa Monica |
| 1 | Cafe Belen |
| 1 | Surpuba Bread and Food |
| 1 | The Mill, Murietta |
| 1 | Ba Ba Loo, Palm Desert |
| 1 | BNP Paribas |
| 1 | Cliffhouse, La Quinta |
| 1 | Black Bear Diner, Colton |
| 1 | Noah's Bagels, MDR |
| 1 | Hamburger Habit |
| 1 | Venice Beach Club, @Rose |
| 1 | Flake, Venice |
| 1 | Pasta Sisters, Culver City |
| 1 | Centinella Café, Culver City |
| 1 | Brass Bird Cafe, Carpinteria |
| 1 | Palisades Lutheran Church |
| 1 | Bike Shed Moto Co, DTLA |
| 1 | Palm Cafe, La Quinta |
| 1 | Beethoven Market |
| 1 | Hopdoddy, Playa del Rey |
| 1 | The Cloverfield |
| 1 | Sauced, Redondo Beach |
| 1 | Bread Basket, Tustin |
| 1 | Keedy's, La Quinta |
| 1 | Broken Spanish |
| 1 | Leo Carrillo |
| 1 | Lutheran Church of the Palisades |
| 1 | Nancy's prediction on March 2, 2015 |

### `data/seeds/mahjongg/mahjongg_demo_2026-06-22.xlsx`

10 Where cells, 5 distinct.

| Count | Name |
|------:|------|
| 4 | The Club |
| 2 | Mike's Place |
| 2 | The Cabin |
| 1 | Lodge |
| 1 | Treehouse |

### `data/seeds/pickleball/pickleball_demo_2026-07-04.xlsx`

20 Where cells, 15 distinct.

| Count | Name |
|------:|------|
| 6 | Freedom Park, Palm Desert, CA |
| 1 | Memorial Park, Los Angeles, CA |
| 1 | Holiday Park, Fort Lauderdale, FL |
| 1 | Louis Sutter, San Francisco, CA |
| 1 | Green Lake, Seattle, WA |
| 1 | Cole Park, Dallas, TX |
| 1 | Belknap Park, Grand Rapids, MI |
| 1 | Pan American Park, Austin, TX |
| 1 | Plummer Park, Los Angeles, CA |
| 1 | Poinsettia Park, Carlsbad, CA |
| 1 | Riverside Park, New York, NY |
| 1 | Sawyer Point, Cincinnati, OH |
| 1 | Sunset Park, Las Vegas, NV |
| 1 | Turkey Thicket, Washington, DC |
| 1 | Willow Park, Park City, UT |

### `data/seeds/progressiverummy/progressiverummy_demo_2026-06-22.xlsx`

434 Where cells, 39 distinct.

| Count | Name |
|------:|------|
| 208 | Preston |
| 129 | Superior |
| 32 | Palm Desert |
| 9 | Sally's |
| 5 | Lake Tahoe Campground |
| 4 | Cedros |
| 4 | San Angelo, TX |
| 3 | Thornehill Broome |
| 3 | Azalea, Sequoia |
| 2 | Hobson Beach Park, Ventura |
| 2 | Emma Wood St Bch |
| 2 | Tahoe City Campground |
| 2 | Anza Borrego State Park ￼￼ |
| 2 | Carpenteria |
| 2 | Huntington Beach |
| 2 | Newport Dunes |
| 1 | Steckel Camp, Santa Paula, CA |
| 1 | Aspen Camp, Lee VIning, CA |
| 1 | Indian Wells |
| 1 | Rincon Parkway |
| 1 | Preston - Passover |
| 1 | Bridgeport |
| 1 | Mariposa Fairgrounds |
| 1 | Tuscon, AZ |
| 1 | Fort Stockton, TX |
| 1 | Sonora, TX |
| 1 | Cracker Barrel, San Antonio, TX ￼ |
| 1 | Mustang Hollow, TX |
| 1 | San Antonio, TX |
| 1 | Shriner Park, Junction, TX |
| 1 | Van Horn, TX |
| 1 | KOA, Lordsburg, TX |
| 1 | Tonopah, AZ |
| 1 | Robert's Trucks, San Angelo |
| 1 | El Paso |
| 1 | Los Baños |
| 1 | Lue Heron, Tillamook |
| 1 | Morro Bay |
| 1 | Aurora's House |

### `data/seeds/progressiverummy/progressiverummy_seed_2026-06-16.xlsx`

539 Where cells, 48 distinct.

| Count | Name |
|------:|------|
| 260 | Preston |
| 146 | Superior |
| 38 | Palm Desert |
| 23 | Sally's |
| 5 | Lake Tahoe Campground |
| 4 | Cedros |
| 4 | Port Aransas, TX |
| 4 | San Angelo, TX |
| 3 | Indian Wells |
| 3 | Thornehill Broome |
| 3 | Azalea, Sequoia |
| 2 | Steckel Camp, Santa Paula, CA |
| 2 | Campland on the Bay, San Diego |
| 2 | Hobson Beach Park, Ventura |
| 2 | Emma Wood St Bch |
| 2 | Tahoe City Campground |
| 2 | Anza Borrego State Park ￼￼ |
| 2 | Carpenteria |
| 2 | Huntington Beach |
| 2 | Newport Dunes |
| 1 | <?> |
| 1 | Ian's House |
| 1 | Refugio St. Beach |
| 1 | Aspen Camp, Lee VIning, CA |
| 1 | Goleta |
| 1 | Rincon Parkway |
| 1 | Preston - Passover |
| 1 | Bridgeport |
| 1 | Mariposa Fairgrounds |
| 1 | Tuscon, AZ |
| 1 | Fort Stockton, TX |
| 1 | Sonora, TX |
| 1 | Cracker Barrel, San Antonio, TX ￼ |
| 1 | Mustang Hollow, TX |
| 1 | San Antonio, TX |
| 1 | Shriner Park, Junction, TX |
| 1 | Van Horn, TX |
| 1 | KOA, Lordsburg, TX |
| 1 | Tonopah, AZ |
| 1 | Robert's Trucks, San Angelo |
| 1 | El Paso |
| 1 | Sancola |
| 1 | Los Baños |
| 1 | Lue Heron, Tillamook |
| 1 | Morro Bay |
| 1 | Dakota Trail |
| 1 | Debby's House |
| 1 | Last row of conditional formatting |
