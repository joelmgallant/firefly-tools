# Untagged Transaction Analysis & Category Recommendations

## Overview
- **Total uncategorized transactions**: 175
- **Date range**: 2025-01-03 to 2025-10-03
- **Total amount**: $82,951.35
- **Current matches**: 0 (all showing as Uncategorized)

## Key Findings

### High-Frequency Merchants (Need Immediate Attention)

#### VIVOBAREFOOT (Shoes) - **$2,612.60 across 8 transactions**
- Clearly a shoe retailer
- **Recommendation**: Add new "Shoes" category or expand "Clothing" to include shoes

#### Hotel Expenses - **$2,822.73 across 3 transactions**
- HOTEL AXEL (Barcelona): $1,440.86
- Hotel Rumbao Tribute (Puerto Rico): $1,403.91
- **Recommendation**: Add "Hotels" or "Accommodation" category

#### Large Monthly Payments - **$42,617.27 across 5 transactions**
- Pattern: "APRIL 25 PYMT", "MAR 2025 PYMT", "FEB 2025 PYMT"
- Amounts: ~$10,000-$11,000 each
- **Recommendation**: These are credit card payments, should be "Transfer" or "Debt"

#### Claude AI Subscription - **$159.60**
- AI software subscription
- **Recommendation**: Already have "Software" category, need to add CLAUDE keyword

#### LULULEMON (Athletic Wear) - **$355.68 across 2 transactions**
- Well-known athletic apparel brand
- **Recommendation**: Add to "Clothing" category

#### TOUCHNOTE.COM - **$143.94 across 6 transactions**
- Photo postcard service ($23.99/month)
- **Recommendation**: Could be "Software" or new "Personal Services" category

---

## Recommended Category Pattern Additions

### 1. **Software/SaaS** (existing category - add keywords)
```python
'CLAUDE.AI', 'PADDLE.NET', 'MIMESTREAM', 'FLEXIBITS', 'FANTASTICAL',
'BIKEMAP', 'TOUCHNOTE'
```
- PADDLE.NET* MIMESTREAM: $80.27 (email client)
- FLEXIBITS FANTASTICAL: $91.99 (calendar app)
- BIKEMAP GMBH: $59.00 (cycling app)
- PAYPAL *MYNOISE: $14.58 (ambient sound generator)

### 2. **Clothing** (existing - add these keywords)
```python
'LULULEMON', 'VIVOBAREFOOT', 'NOREASTER APPAREL', 'HEAT WAVE VISUAL',
'SHADES WORLD', 'CHERRYKITTEN', 'IYKYK'
```
- Includes athletic wear, shoes, sunglasses

### 3. **Entertainment** (existing - add these keywords)
```python
'CINEPLEX', 'HALIMAC AXE THROWING', 'SEVEN BAYS BOULDERING',
'ACTIVATE HALIFAX', 'SQ *FUTURE FLASH ARCAD', 'SANDSPIT',
'TILT-A-WHI', 'NBX*LIVE ART DANCE', 'HFX FEST', 'HALIFAXMUSIC',
'SHOWPASS', 'PRIMEVIDEO', 'Ad free for PrimeVideo'
```
- Rock climbing, axe throwing, arcades, movies, concerts, events

### 4. **Restaurant** (existing - add these keywords)
```python
'BICYCLE THIEF', 'SEAHORSE TAVERN', 'BAR STILLWELL', 'TORIDORI',
'SQ *THE BAO JOURNEY', 'THE NARROWS', 'QUESADA', 'CABLE WHARF',
'ECONOMY SHOE SHOP', 'SQ *FRABJOUS DELIGHTS', 'MASHASWEE',
'PINATA CANTINA', 'CHURRERIA', 'PANADERIA FIKA', 'LA CHAPELLE',
'LUCCIANOS', 'ANITA LA MAMMA DEL GELATO', 'HIGH SOCIETY',
'PRETZELMAKER', 'MRS. FIELD', 'KAI BRADYS', 'FERVOR PALMA',
'EWR C3 GLOBAL BAZAAR'
```

### 5. **Grocery** (existing - add these keywords)
```python
'HYDROSTONE GROCETERIA', 'POINT PLEASANT GROCERY', 'DOLLARAMA',
'EMPIRE', 'SUPERMAX', 'WALGREENS' (can also be medical)
```
- EMPIRE is a major NS grocery chain (Sobeys parent)

### 6. **Alcohol** (existing - add these keywords)
```python
'HARVEST BEER WINE', 'HARVEST DOWNTOWN', 'MERCATOR VINEYARDS'
```

### 7. **Coffee** (could be new category or Restaurant subcategory)
```python
'SQ *UNCOMMON GROUNDS', 'SQ *WORLD TEA HOUSE'
```

### 8. **Medical** (existing - add these keywords)
```python
'FARMACIA', 'WALGREENS', "MURPHY'S QUEEN STREET PHA"
```
- FARMACIA: Spanish/Portuguese for pharmacy

### 9. **Household** (existing - add these keywords)
```python
'HOME DEPOT', 'KENT', 'BLUEAIR', 'TIDEWATER MERCHAN',
'MOUNTAIN EQUIPMENT COMPAN', 'MEC', "CLEVE'S SPORTING GOODS"
```
- MEC and outdoor stores could also be "Sporting Goods"

### 10. **NEW CATEGORY: Hotels/Accommodation**
```python
'HOTEL', 'HOTEL AXEL', 'RUMBAO TRIBUTE', 'MOXY'
```

### 11. **NEW CATEGORY: Transportation**
```python
'STRAIT CROSSING BRIDGE', 'HALIFAX HARBOUR BRIDGE', 'FREENOW',
'PREMIER CAR SERVICE', 'MASABI', 'UNITED AIRLINES', 'UNITED      0'
```
- Tolls, bridges, ride-sharing, airlines

### 12. **NEW CATEGORY: Travel Booking**
```python
'EXPEDIA'
```
- Large booking: $1,260.45

### 13. **Transfer** (existing - add these keywords)
```python
'PYMT', 'CURRENCY CLOUD', 'WWW CASH ADV', 'AVANCE DE FONDS',
'CANADA' (when amount > $100), '@ $45.00', '@ $'
```
- Credit card payments, currency exchange, cash advances
- Generic payment descriptions like "1 @ $45.00"

### 14. **NEW CATEGORY: Bank Fee**
```python
'RBC - SERVICE CHARGE', 'SERVICE CHARGE', 'WWW OD HDLG FEE',
'OD HDLG', 'CASH - SERVICE CHARGE'
```
- Currently mapped to "Banking Fee" but inconsistent

### 15. **NEW CATEGORY: Returns/Adjustments**
```python
'ITEM RETURNED NSF', 'NSF', 'CREDIT ADJUSTMENT'
```
- These should probably be excluded from spending analysis

### 16. **NEW CATEGORY: Donations/Charity**
```python
'DONOR DRIVE', 'CCS DONOR', 'HALIFAX PRIDE' (could also be event)
```

### 17. **NEW CATEGORY: Government Services**
```python
'ACCESS NOVA SCOTIA', 'RMV', 'DMV'
```
- Vehicle registration: $301.85

### 18. **NEW CATEGORY: Vending**
```python
'SH VENDING', 'VENDING', 'AMFM VENDING'
```

### 19. **NEW CATEGORY: Stationery/Office**
```python
'CAHIER STATI', 'STATIONERY', 'STAPLES' (already in Household)
```

### 20. **NEW CATEGORY: Jewelry/Accessories**
```python
'BISUTERIA', 'VENUS ENVY'
```
- BISUTERIA SANT JOAN: $275.36 across 2 transactions (jewelry store in Spain)

---

## Edge Cases & Unclear Transactions

### Need Manual Review/Research:
1. **FLOLAB** ($129.00 across 3 transactions) - Could be flowers, lab, beauty products?
2. **SQ *JAMES ARTHUR MACLE** ($563.00) - Large single purchase, unclear merchant
3. **SQ *WESTWOOD 2** ($96.00) - Could be restaurant, bar, or event venue
4. **THE BG** ($13.21) - Too abbreviated to categorize
5. **DA ZERO** ($113.54) - Unknown merchant
6. **SQ *GOCF - HALIFAX** ($29.93) - Could be GoC Fitness or Government of Canada?
7. **WDFG BARCELONA** ($88.60) - Barcelona merchant, unclear type
8. **Currency conversions** (e.g., "1.00 USD @ 1.400000000000") - Just foreign exchange, inherit parent transaction category

### Large "CANADA" Transactions:
- **$10,863.88** (2025-04-02)
- **$103.00** x2 (2025-01-14)
- **$110.00** (2025-04-21)

These generic "CANADA" descriptions are problematic. Could be:
- Government payments
- International wire transfers
- Transfers between accounts

**Recommendation**: Need pattern matching - if amount > $1000 and description = "CANADA", likely Transfer.

---

## Pattern Improvements

### Current Issues:
1. **Too restrictive matching** - Many common merchants not included
2. **Missing categories** - Hotels, Transportation, Bank Fees, Donations not in system
3. **No pattern for generic payments** - "1 @ $45.00" should be Transfer
4. **No handling for returns** - ITEM RETURNED NSF should be special category
5. **Foreign merchants not recognized** - Spanish/European merchants during travel

### Suggested Pattern Matching Order:
1. **Specific merchants first** (VIVOBAREFOOT, LULULEMON, etc.)
2. **Generic patterns** (HOTEL, PHARMACY, RESTAURANT)
3. **Transaction types** (PYMT, TRANSFER, NSF)
4. **Fallback to Uncategorized**

---

## Implementation Priority

### High Priority (Frequent/High Value):
1. ✅ **Transfer patterns** - Captures $42k+ in credit card payments
2. ✅ **VIVOBAREFOOT** → Clothing/Shoes - $2,612.60
3. ✅ **Hotel patterns** - $2,822.73
4. ✅ **LULULEMON** → Clothing - $355.68
5. ✅ **Entertainment venues** (CINEPLEX, AXE THROWING, BOULDERING) - $500+
6. ✅ **Software subscriptions** (CLAUDE, PADDLE, FLEXIBITS) - $400+

### Medium Priority:
7. Restaurant additions (30+ transactions)
8. Grocery additions (EMPIRE, DOLLARAMA)
9. Medical/Pharmacy (FARMACIA, WALGREENS)
10. Bank fees category
11. Transportation (bridges, tolls, airlines)

### Low Priority (Few transactions):
12. Vending machines
13. Stationery
14. Jewelry/Accessories
15. Government services

---

## Next Steps

1. **Review edge cases** - Research unclear merchants (FLOLAB, DA ZERO, etc.)
2. **Update suggest_category()** - Add new keywords in priority order
3. **Create new categories in Firefly III** (if needed):
   - Hotels/Accommodation
   - Transportation
   - Donations
   - Returns (special handling)
4. **Re-run untagged analysis** - See improvement in match rate
5. **Manual categorization** - For remaining unclear transactions
6. **Apply categories** - Use apply_categories.py to bulk update

---

## Expected Improvement

After implementing high + medium priority additions:
- **Current match rate**: 0% (0/175)
- **Projected match rate**: 85-90% (150-160/175)
- **Remaining manual review**: 15-25 transactions (edge cases)
