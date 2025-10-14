"""
Parse category patterns from money.py and save to JSON for analysis.
"""

import json
from pathlib import Path

# Import the suggest_category function to extract patterns
import sys
sys.path.insert(0, str(Path(__file__).parent))

def extract_category_patterns():
    """Extract category patterns from the suggest_category function"""

    # Category patterns from suggest_category() in money.py
    category_patterns = {
        # Special cases - check first
        'Returns': ['ITEM RETURNED NSF', 'NSF', 'CREDIT ADJUSTMENT'],
        'Income': ['UBIQUE NETWORKS', 'NET PAY', 'INITIAL CARRYOVER'],
        'Trip-Iceland': ['ISK @'],

        # Banking & Transfers
        'Transfer': ['TRANSFER', 'TFR', 'WWW TRF DDA', 'PAYMENT - THANK YOU', 'PAIEMENT - MERCI',
                    'ROYAL BANK OF CANADA', 'PYMT', 'CURRENCY CLOUD', 'WWW CASH ADV',
                    'AVANCE DE FONDS', '@ $', 'USD @', 'EUR @', 'INTERAC NTWK/RESEAU'],
        'Banking Fee': ['MONTHLY FEE', 'ANNUAL FEE', 'BANK FEE', 'RBC - SERVICE CHARGE',
                       'SERVICE CHARGE', 'WWW OD HDLG FEE', 'OD HDLG', 'CASH - SERVICE CHARGE',
                       'RBC ROYAL BANK', 'CASH ADVANCE FEE', 'DEC 2024 FEES'],
        'Debt': ['LOAN PMT', 'BILL PMT', 'WWW PMT', 'AFFIRM', 'WWW PAYMENT', 'AMEX REGULAR',
                'CAPITAL ONE M', 'PAYBRIGHT'],

        # Shopping
        'Electronics': ['FLOLAB', 'BLUEAIR', 'BEST BUY', 'BLACKMAGIC CLOUD'],
        'Clothing': ['SIMONS', 'H&M', 'ZARA', 'GAP', 'NIKE', 'ADIDAS', 'WORK AUTHORITY',
                    'VIVOBAREFOOT', 'LULULEMON', 'NOREASTER APPAREL', 'HEAT WAVE VISUAL',
                    'SHADES WORLD', 'CHERRYKITTEN', 'IYKYK', 'AVIATOR NATION', 'LEATHER MAN INC',
                    "LEVI'S", 'LACOSTE'],
        'Jewelry': ['BISUTERIA', 'VENUS ENVY'],
        'Household': ['CANADIAN TIRE', 'IKEA', 'STAPLES', 'LONG & MCQUADE', 'FREAK LUNCHBOX',
                     'HOME DEPOT', 'KENT', 'TIDEWATER MERCHAN', 'MOUNTAIN EQUIPMENT COMPAN',
                     'MEC', "CLEVE'S SPORTING GOODS", 'WAL-MART', 'WALMART', 'ATLANTIC GARDENS',
                     'WINNERS', 'HOMESENSE', 'MICHAELS', 'GIANT TIGER'],

        # Food & Drink
        'Alcohol': ['NSLC', 'GARRISON BREWING', 'GOOD ROBOT', 'PROPELLER BREWING', 'BULWARK CIDER',
                   '2 CROWS BREWING', 'BISHOPS CELLAR', 'OAK TREE LIQUOR', 'LIQUOR STORE',
                   'TOOTHY MOOSE', 'WEST ROYALTY LIQUOR', 'HARVEST BEER WINE', 'HARVEST DOWNTOWN',
                   'MERCATOR VINEYARDS', 'CHAIN YARD CIDER', 'SQ *PROPELLER B', 'BRASSERIE MCAUSLAN',
                   'ALCOOL NB LIQUOR'],
        'Food Delivery': ['DOORDASH', 'SKIPTHEDISHES', 'DD/DOORDASH'],
        'Restaurant': ['RESTAURANT', 'CAFE', 'COFFEE', 'PIZZA', 'BURGER', 'SUSHI', 'DINING',
                      'TIM HORTON', 'STARBUCKS', 'SUBWAY', 'MCDONALD', 'WENDY', 'A&W',
                      'CHATIME', 'ANTOJO TACO', 'MASHAWEE', 'MASHASWEE', 'A TASTE OF INDIA', 'CAFFE LUCCA',
                      'AU LIBAN', 'BONEHEADS BBQ', 'DURTY NELLYS', 'STUBBORN GOAT', 'THE PINT',
                      "DAVE'S LOBSTER", 'SALT & ASH', 'JACK ASTOR', 'KFC', 'DAIRY QUEEN',
                      'RISTORANTE', 'BOOSTER JUICE', 'WEIRD HARBOUR', 'STEVE-O-RENO',
                      'THE MIDDLE SPOON', 'MERCANTILE SOCIAL', 'STARDUST BAR',
                      'BICYCLE THIEF', 'SEAHORSE TAVERN', 'BAR STILLWELL', 'TORIDORI',
                      'SQ *THE BAO JOURNEY', 'THE NARROWS', 'QUESADA', 'CABLE WHARF',
                      'ECONOMY SHOE SHOP', 'SQ *FRABJOUS DELIGHTS', 'PINATA CANTINA',
                      'CHURRERIA', 'PANADERIA FIKA', 'LA CHAPELLE', 'LUCCIANOS',
                      'ANITA LA MAMMA DEL GELATO', 'HIGH SOCIETY', 'PRETZELMAKER',
                      'MRS. FIELD', 'KAI BRADYS', 'FERVOR PALMA', 'EWR C3 GLOBAL BAZAAR',
                      'SQ *UNCOMMON GROUNDS', 'SQ *WORLD TEA HOUSE', 'TAQUILLA',
                      'PASQUIER', 'NEW GLASGOW LOBSTER', 'PITA PIT', 'CANTON SAIGON', 'PUR & SIMPLE',
                      'INDOCHINE BANH MI', 'MEZZA LEBANESE', 'PUMP HOUSE', 'TWO DOORS DOWN',
                      'HELIUM COMEDY', 'GONG CHA', 'CHUNGCHUN HOTDOG', "WILLY'S FRESH CUT",
                      'TSUJIRI', "JOHNNY", 'CARNEGIE DINER', 'DENNY', 'CORNER BAKERY',
                      'WESTSIDE MARKET', 'CROSSOVER', 'SHAKE SHACK', 'FRESHLY SQUEEZED',
                      "LULU'S PASTA BAR", 'KRAVE SPRING', "DAVE'S FRUIT", 'BAR LE CAMPUS',
                      'LE PETIT', 'MANCHU WOK', 'TACO BOYZ', 'AFRITE KITCHEN', 'FIVE GUYS',
                      'BAKERY', 'TURBO CHICKEN', 'TRIDENT BOOKSELLERS', 'SAPORI ITALIAN',
                      'MELTWICH', 'CANTON', 'PUMP HOUSE BREWPUB', 'DRIFT SALON & BAR',
                      'SMOKEY HOUSE', 'LIONS HEAD TAVERN', 'WATER STREET WILSON', 'CRAFT BEER',
                      'UNCOMMON GROUNDS', 'PORT PUB', 'MAXWELLS PLUM', 'PROXI DUTCH',
                      'NOOK AND CRANNY', 'BOTROW', 'NOGGINS CORNER', 'GREIG POTTERY',
                      '540 NORTH', 'TRAIN STATION BIKE', 'ESCONDITE', 'BAR RENARD', 'NINE LOCKS',
                      'THE CANTEEN', 'DOGS ON WHEELS', 'DRIFT SALON', 'BOATHOUSE BITES',
                      "HARRY'S DAIRY", 'FIDDLING FISHERMA', 'YUKYUKS', 'HIMALAYAN CURRY',
                      'AUCTION HOUSE', 'THORNBLOOM', 'ELI AND TRIX', 'GOBONG', 'HOUSE FRIENDS',
                      'FINN FOLK', 'LFBAKERY', 'EAST COAST BAKERY', 'ONROUTE', 'HUDSON ST',
                      'DUNKIN', 'MILANO', 'CAVICCHI', 'FOG COMPANY', 'LANE FARMS',
                      'BEIRUT WAY', 'TST-', 'TST*', 'SUDA TABLE', 'SEBASTIANS NEWS',
                      'MTA*NYCT', 'AMC ONLINE', 'BOWL', 'CHESS PIECE', 'SNOOTY FOX',
                      'BROWN HOUND', 'BREAD N WINE', 'PARTYBOY', 'OWLS HOLLOW', 'DA ZERO',
                      'BROADWAY', 'PRE ROLL WORLD', 'STILLWELL BREWING'],
        'Dessert': ['COWS', 'DAIRY BAR', 'BLACK BEAR ICE CREAM', 'ICE CREAM', 'GELATO',
                   'PANADERIA', 'AMORINO', 'GELATERIA', 'LA MAMMA DEL GELATO',
                   'CHOCOLAT', 'ROUSSEAU CHOCOLAT', 'MAGNOLIA BAKERY'],
        'Grocery': ['SOBEYS', 'SUPERSTORE', 'WHOLEFDS', 'WALMART', 'COSTCO', 'LOBLAWS', 'METRO',
                   'MASSTOWN MARKET', 'ARTHUR\'S URBAN MARKET', 'PRICE MART', 'NEEDS', 'CO-OP',
                   'HIGHMART', 'NOVA GROCERY', 'E-JOY FOOD MART', 'MISHOO\'S VARIETY',
                   'L.A.SMITH CONVENIENCE', 'HYDROSTONE GROCETERIA', 'POINT PLEASANT GROCERY',
                   'DOLLARAMA', 'EMPIRE', 'SUPERMAX', 'GETAWAY BUTCHER', 'MR SEAFOOD',
                   'WINSLOE CONVENIENCE', 'LOCAL SOURCE', 'JEAN COUTU', 'VALUE VILLAGE',
                   'COUCHE-TARD', 'MARKET', 'DEPANNEUR', 'FARGI', 'RAFI SUPERMARKET',
                   'PROXIM SUPERMERCATS', 'STUYTOWN MARKETPLACE', 'SEAFOOD', 'LOBSTER',
                   'SALLY BEAUTY', 'HANDPIE COMPANY', 'CAVENDISH TOURIST', 'DESERRES'],

        # Transportation & Travel
        'Hotels': ['HOTEL AXEL', 'HOTEL RUMBAO', 'RUMBAO TRIBUTE', 'MOXY HALIFAX', 'HOTEL',
                  'FOUR POINTS BY SHERATO'],
        'Transportation': ['STRAIT CROSSING BRIDGE', 'HALIFAX HARBOUR BRIDGE', 'FREENOW',
                          'PREMIER CAR SERVICE', 'MASABI', 'UNITED      0', 'UNITED AIRLINES',
                          'MTA*NYCT PAYGO', 'STM', 'A30 EXPRESS'],
        'Travel Booking': ['EXPEDIA', 'FLIGHTCONNECTIONS'],
        'Travel': ['AIR CAN', 'AIRCANADA', 'FORA TRAVEL', 'GETNOMAD', 'VIRGIN VOYAGES',
                  'VIRGIN CRUISE', 'WESTJET', 'DELTA AIR'],
        'Taxi': ['UBER', 'LYFT', 'TAXI', 'REVEL', 'BIRD', 'MOVE SCOOTER', 'HFXESCOOTERS'],
        'Gas': ['PETRO', 'IRVING', 'SHELL', 'ESSO', 'MOBIL', 'CIRCLE K', 'ULTRAMAR',
               'CDN TIRE GASBAR', 'FAST FUEL'],

        # Utilities & Services
        'Utilities': ['EASTLINK', 'TELUS', 'BELL', 'ROGERS', 'NSPI', 'ELECTRIC', 'VOIP.MS'],
        'Software': ['AMAZON WEB SERVICES', 'AWS', 'ADOBE', 'MICROSOFT', 'APPLE', 'GOOGLE', 'OPENAI', 'CHATGPT',
                    'KAGI.COM', 'SERIF', 'OCULUS', 'TRANSUNION', 'CLAUDE.AI', 'PADDLE.NET',
                    'MIMESTREAM', 'FLEXIBITS', 'FANTASTICAL', 'TOUCHNOTE', 'BIKEMAP',
                    'PAYPAL *MYNOISE', 'OTTER.AI', 'COURSRA', 'SIMPLETAX', 'BITWARDEN',
                    'RUNPOD.IO', 'VAGON INC', 'DRI*NVIDIA', 'TWITCH', 'SMIGHT-TIP',
                    'ITCH.IO', 'VPN*', 'NINTENDO', 'GODADDY'],
        'Amazon': ['AMZN', 'AMAZON'],
        'Shipping': ['UPS'],

        # Entertainment
        'Entertainment': ['NETFLIX', 'SPOTIFY', 'DISNEY', 'PRIME VIDEO', 'PRIMEVIDEO',
                         'Ad free for PrimeVideo', 'YOUTUBE', 'PSN', 'STEAM',
                         'CRUNCHYROLL', 'PATREON', 'SONY INTERACTIVE', 'FUTURE FLASH ARCADE',
                         'EVENTBRITE', 'SPIRIT HALLOWEEN', 'NAUTICUS', 'MARITIME FUN GROUP',
                         'AMBASSATOURS', 'HARBOUR QUEEN', 'CULTURE LINK', 'PLAYSTATION NETWORK',
                         'STEAMGAMES', 'CINEPLEX', 'HALIMAC AXE THROWING', 'SEVEN BAYS BOULDERING',
                         'ACTIVATE HALIFAX', 'SQ *FUTURE FLASH ARCAD', 'SANDSPIT', 'TILT-A-WHI',
                         'NBX*LIVE ART DANCE', 'HFX FEST', 'HALIFAXMUSIC', 'SHOWPASS',
                         'PEACOCK', 'SOHO HOUSE', 'SHINDIG', 'GALLERY', 'ZWICKER',
                         'DROPOUT', 'FEVER*', 'BEAR BALL', 'SCIENCE & HUMANS', 'WET  N WILD',
                         'MARITIME BUS', 'AMBASSATOURS', 'BOOK OF MORMON', 'GLOW THE EVENT',
                         'AXE MANAGEMENT', 'PIE OH MY', 'PEI CMC', "QUEEN'S MARQUE"],

        # Health & Personal
        'Medical': ['PHARMACY', 'DRUG', 'DENTAL', 'DOCTOR', 'CLINIC', 'HOSPITAL',
                   'BAYSHORE HEALTHCARE', 'LAWTONS', 'SUNLIFE', 'QEII FOUNDATION',
                   'SUPPLEMENT KING', 'NOVA GP', 'FARMACIA', 'WALGREENS', "MURPHY'S QUEEN STREET PHA",
                   'MEDICINE SHOPPE', 'SIGNATURE HEALTH', 'KEYSTONE HEALTH', 'PERIODONTICS',
                   'SLEEP THERAPUTICS', 'BEDFORD PERIODONTICS', 'QEII PARKING'],
        'Personal Care': ['BARBERSHOP', 'BARBER', 'SEPHORA', 'DANIELS TAILORS', 'UVAPESHOP',
                         'ONE BLOCK BABERSHOP', 'DOLLAR SHAVE CLUB', 'SPA', 'VITALITY MEDI',
                         'HIGHLANDER SPA', 'PURE VISION', 'ALCONE COMPANY', 'FITTED CLOSET',
                         'DULY NOTED', 'MOONSNAIL SOAPWORKS'],
        'Vaping': ['VAPE', 'TWENTY-FOUR ELEVEN VAP'],

        # Other
        'Vehicle': ['PARKING', 'CAR WASH', 'AUTO', 'ACCESS NOVA SCOTIA-RMV',
                   'QEII PARKING', 'POWNALL PARKADE', 'PARK INDIGO', 'HRM ON-LINE PARKING'],
        'Donations': ['DONOR DRIVE', 'CCS DONOR', 'HALIFAX PRIDE', 'WIKIMEDIA', 'BIDEAWHILE'],
        'Vending': ['SH VENDING', 'VENDING', 'AMFM VENDING'],
        'Legal': ['NS JUSTICE', 'JUSTICE ONLINE PAYMENT'],
    }

    return category_patterns

def main():
    """Parse patterns and save to JSON"""

    print("Extracting category patterns from money.py...")

    patterns = extract_category_patterns()

    # Count total keywords
    total_keywords = sum(len(keywords) for keywords in patterns.values())

    print(f"Found {len(patterns)} categories with {total_keywords} total keywords\n")

    # Save to JSON file
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)

    output_path = data_dir / "category_patterns.json"

    with open(output_path, 'w') as f:
        json.dump(patterns, f, indent=2)

    print(f"Saved patterns to {output_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("CATEGORY PATTERNS SUMMARY")
    print("=" * 80)

    for category in sorted(patterns.keys()):
        keywords = patterns[category]
        print(f"{category}: {len(keywords)} keywords")

if __name__ == "__main__":
    main()
