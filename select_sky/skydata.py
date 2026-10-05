"""Lookup tables for Select Sky: airlines, aircraft types, airports.

Pure data plus a few small functions, with no imports, so it loads on the badge as is.
Names are ASCII because the pixel fonts have no accents. Airline colours are brand
colours darkened until white text on them has WCAG contrast of at least 4.5.
Codes were checked against OpenFlights and Virtual Radar Server airline lists, types
against the ICAO Doc 8643 designators, and airports against OurAirports.
"""

# ICAO callsign prefix: (name, IATA code, brand colour)
AIRLINES = {
    "AAL": ("American", "AA", (0, 114, 198)),
    "AAR": ("Asiana", "OZ", (200, 16, 38)),
    "AAY": ("Allegiant", "G4", (0, 76, 151)),
    "ABX": ("ABX Air", "GB", (0, 56, 112)),
    "ABY": ("Air Arabia", "G9", (200, 20, 35)),
    "ACA": ("Air Canada", "AC", (196, 18, 48)),
    "AEA": ("Air Europa", "UX", (0, 62, 140)),
    "AEE": ("Aegean", "A3", (0, 53, 128)),
    "AFR": ("Air France", "AF", (0, 33, 87)),
    "AIC": ("Air India", "AI", (170, 24, 48)),
    "AIQ": ("Thai AirAsia", "FD", (200, 10, 20)),
    "AMX": ("Aeromexico", "AM", (11, 35, 86)),
    "ANA": ("ANA", "NH", (0, 55, 145)),
    "ANZ": ("Air New Zealand", "NZ", (24, 24, 28)),
    "APJ": ("Peach", "MM", (185, 0, 100)),
    "ARG": ("Aerolineas Arg.", "AR", (0, 100, 150)),
    "ASA": ("Alaska", "AS", (1, 66, 106)),
    "ASH": ("Mesa Airlines", "YV", (0, 60, 120)),
    "ATN": ("Air Transport Intl", "8C", (0, 56, 112)),
    "AUA": ("Austrian", "OS", (200, 18, 38)),
    "AVA": ("Avianca", "AV", (200, 30, 40)),
    "AXB": ("Air India Exp.", "IX", (200, 30, 40)),
    "AXM": ("AirAsia", "AK", (200, 10, 20)),
    "AZU": ("Azul", "AD", (0, 50, 150)),
    "BAW": ("British Airways", "BA", (7, 90, 170)),
    "BCS": ("EAT Leipzig", "QY", (200, 12, 20)),
    "BEL": ("Brussels Air.", "SN", (0, 35, 100)),
    "BKP": ("Bangkok Airways", "PG", (0, 80, 160)),
    "BOX": ("AeroLogic", "3S", (200, 12, 20)),
    "CAL": ("China Airlines", "CI", (200, 20, 80)),
    "CBJ": ("Beijing Capital", "JD", (190, 22, 40)),
    "CCA": ("Air China", "CA", (200, 16, 32)),
    "CEB": ("Cebu Pacific", "5J", (0, 80, 160)),
    "CES": ("China Eastern", "MU", (0, 64, 148)),
    "CFE": ("BA CityFlyer", "CJ", (20, 50, 118)),
    "CFG": ("Condor", "DE", (140, 108, 0)),
    "CHH": ("Hainan Airlines", "HU", (190, 22, 40)),
    "CLX": ("Cargolux", "CV", (0, 60, 130)),
    "CMP": ("Copa", "CM", (0, 82, 159)),
    "CPA": ("Cathay Pacific", "CX", (0, 98, 92)),
    "CQH": ("Spring Airlines", "9C", (0, 120, 60)),
    "CSN": ("China Southern", "CZ", (0, 80, 160)),
    "CSZ": ("Shenzhen Air", "ZH", (200, 16, 32)),
    "CXA": ("Xiamen Air", "MF", (0, 80, 160)),
    "DAL": ("Delta", "DL", (200, 16, 46)),
    "DHK": ("DHL Air UK", "D0", (200, 12, 20)),
    "DLH": ("Lufthansa", "LH", (5, 22, 77)),
    "EDV": ("Endeavor Air", "9E", (160, 20, 40)),
    "EDW": ("Edelweiss", "WK", (190, 20, 40)),
    "EIN": ("Aer Lingus", "EI", (0, 112, 72)),
    "EJA": ("NetJets", "1I", (90, 90, 90)),
    "EJU": ("easyJet Europe", "EC", (190, 70, 0)),
    "ELY": ("El Al", "LY", (0, 56, 130)),
    "ENY": ("Envoy Air", "MQ", (0, 64, 128)),
    "ESR": ("Eastar Jet", "ZE", (190, 20, 30)),
    "ETD": ("Etihad", "EY", (150, 104, 48)),
    "ETH": ("Ethiopian", "ET", (0, 110, 60)),
    "EVA": ("EVA Air", "BR", (0, 115, 70)),
    "EWG": ("Eurowings", "EW", (168, 0, 92)),
    "EXS": ("Jet2", "LS", (196, 16, 34)),
    "EZS": ("easyJet Swiss", "DS", (190, 70, 0)),
    "EZY": ("easyJet", "U2", (190, 70, 0)),
    "FDB": ("flydubai", "FZ", (180, 70, 0)),
    "FDX": ("FedEx", "FX", (77, 20, 140)),
    "FFT": ("Frontier", "F9", (0, 110, 56)),
    "FIN": ("Finnair", "AY", (10, 30, 110)),
    "FLE": ("Flair", "F8", (0, 110, 56)),
    "GEC": ("Lufthansa Cargo", "LH", (5, 22, 77)),
    "GFA": ("Gulf Air", "GF", (170, 66, 0)),
    "GIA": ("Garuda Indonesia", "GA", (0, 100, 160)),
    "GJS": ("GoJet", "G7", (0, 70, 130)),
    "GLO": ("Gol", "G3", (178, 72, 0)),
    "GTI": ("Atlas Air", "5Y", (0, 56, 112)),
    "HKE": ("HK Express", "UO", (100, 20, 130)),
    "HVN": ("Vietnam Airlines", "VN", (0, 70, 130)),
    "IBE": ("Iberia", "IB", (200, 16, 38)),
    "ICE": ("Icelandair", "FI", (0, 50, 120)),
    "IGO": ("IndiGo", "6E", (0, 54, 160)),
    "ITY": ("ITA Airways", "AZ", (0, 62, 122)),
    "JAL": ("Japan Airlines", "JL", (200, 16, 46)),
    "JBU": ("JetBlue", "B6", (0, 56, 150)),
    "JIA": ("PSA Airlines", "OH", (0, 64, 115)),
    "JJA": ("Jeju Air", "7C", (190, 80, 0)),
    "JNA": ("Jin Air", "LJ", (200, 20, 25)),
    "JST": ("Jetstar", "JQ", (190, 70, 0)),
    "JSX": ("JSX", "XE", (170, 24, 48)),
    "JZA": ("Jazz", "QK", (196, 18, 48)),
    "KAC": ("Kuwait Airways", "KU", (0, 90, 150)),
    "KAL": ("Korean Air", "KE", (0, 110, 180)),
    "KLC": ("KLM Cityhopper", "WA", (0, 112, 172)),
    "KLM": ("KLM", "KL", (0, 112, 172)),
    "KQA": ("Kenya Airways", "KQ", (190, 20, 30)),
    "LAN": ("LATAM Chile", "LA", (40, 30, 120)),
    "LNI": ("Lion Air", "JT", (200, 20, 25)),
    "LOT": ("LOT Polish", "LO", (17, 40, 95)),
    "LPE": ("LATAM Peru", "LP", (40, 30, 120)),
    "LXJ": ("Flexjet", "", (50, 52, 58)),
    "MAC": ("Air Arabia Maroc", "3O", (200, 20, 35)),
    "MAS": ("Malaysia Air", "MH", (0, 44, 111)),
    "MSC": ("Air Cairo", "SM", (100, 28, 120)),
    "MSR": ("EgyptAir", "MS", (0, 60, 130)),
    "MXD": ("Batik Air Malaysia", "OD", (200, 20, 35)),
    "MXY": ("Breeze", "MX", (0, 106, 128)),
    "NAX": ("Norwegian", "DY", (200, 20, 50)),
    "NJE": ("NetJets Europe", "1I", (90, 90, 90)),
    "NOZ": ("Norwegian", "DY", (200, 20, 50)),
    "PAL": ("Philippine Air", "PR", (0, 51, 160)),
    "PDT": ("Piedmont", "PT", (0, 114, 198)),
    "PGT": ("Pegasus", "PC", (140, 108, 0)),
    "PIA": ("Pakistan Intl", "PK", (0, 100, 55)),
    "POE": ("Porter", "PD", (16, 38, 100)),
    "QFA": ("Qantas", "QF", (200, 0, 20)),
    "QLK": ("QantasLink", "QF", (200, 0, 20)),
    "QTR": ("Qatar Airways", "QR", (93, 6, 45)),
    "QXE": ("Horizon Air", "QX", (1, 66, 106)),
    "RAM": ("Royal Air Maroc", "AT", (170, 20, 36)),
    "ROU": ("Air Canada Rouge", "RV", (196, 18, 48)),
    "RPA": ("Republic Airways", "YX", (0, 66, 130)),
    "RUK": ("Ryanair UK", "RK", (10, 50, 140)),
    "RYR": ("Ryanair", "FR", (10, 50, 140)),
    "SAS": ("SAS", "SK", (10, 20, 90)),
    "SCX": ("Sun Country", "SY", (170, 66, 0)),
    "SEJ": ("SpiceJet", "SG", (190, 20, 30)),
    "SIA": ("Singapore Air", "SQ", (0, 35, 95)),
    "SKW": ("SkyWest", "OO", (0, 90, 160)),
    "SVA": ("Saudia", "SV", (0, 104, 60)),
    "SWA": ("Southwest", "WN", (48, 75, 180)),
    "SWR": ("Swiss", "LX", (200, 0, 20)),
    "SWT": ("Swiftair", "WT", (0, 64, 148)),
    "SXS": ("SunExpress", "XQ", (188, 84, 0)),
    "TAM": ("LATAM Brasil", "JJ", (40, 30, 120)),
    "TAP": ("TAP Air Portugal", "TP", (0, 108, 64)),
    "TGW": ("Scoot", "TR", (140, 108, 0)),
    "THA": ("Thai Airways", "TG", (92, 28, 120)),
    "THY": ("Turkish Airlines", "TK", (200, 16, 30)),
    "TOM": ("TUI Airways", "BY", (200, 20, 40)),
    "TRA": ("Transavia", "HV", (0, 115, 55)),
    "TSC": ("Air Transat", "TS", (0, 80, 150)),
    "TVF": ("Transavia FR", "TO", (0, 115, 55)),
    "TWB": ("T'way Air", "TW", (200, 20, 40)),
    "UAE": ("Emirates", "EK", (200, 16, 46)),
    "UAL": ("United", "UA", (0, 82, 165)),
    "UCA": ("CommuteAir", "C5", (0, 82, 165)),
    "UPS": ("UPS", "5X", (100, 65, 23)),
    "VIR": ("Virgin Atlantic", "VS", (200, 16, 40)),
    "VIV": ("Viva Aerobus", "VB", (0, 120, 55)),
    "VJC": ("VietJet", "VJ", (200, 20, 30)),
    "VJT": ("VistaJet", "", (190, 20, 40)),
    "VLG": ("Vueling", "VY", (140, 108, 0)),
    "VOI": ("Volaris", "Y4", (100, 0, 130)),
    "VOZ": ("Virgin Australia", "VA", (200, 16, 36)),
    "VXP": ("Avelo", "XP", (100, 40, 135)),
    "WEN": ("WestJet Encore", "WR", (0, 108, 118)),
    "WJA": ("WestJet", "WS", (0, 108, 118)),
    "WZZ": ("Wizz Air", "W6", (190, 0, 98)),
}

# Military callsign prefixes (REACH is RCH, CONVOY is CNV, ASCOT is RRR and so on).
MILITARY = (
    "BAF", "CFC", "CNV", "FAF", "GAF", "IAM", "PAT", "RCH", "RRR", "SAM",
)
MIL_COLOUR = (70, 86, 60)

# ICAO type designator: short marketing name
TYPES = {
    "A109": "AW109", "A124": "An-124 Ruslan", "A139": "AW139", "A19N": "A319neo",
    "A20N": "A320neo", "A21N": "A321neo", "A306": "A300-600", "A310": "A310", "A318": "A318",
    "A319": "A319", "A320": "A320", "A321": "A321", "A332": "A330-200", "A333": "A330-300",
    "A337": "Beluga XL", "A338": "A330-800", "A339": "A330-900", "A346": "A340-600",
    "A359": "A350-900", "A35K": "A350-1000", "A388": "A380", "A400": "A400M Atlas",
    "AS50": "H125 Squirrel", "AS55": "AS355 Ecureuil 2", "AS65": "AS365 Dauphin",
    "AT45": "ATR 42-500", "AT46": "ATR 42-600", "AT72": "ATR 72", "AT75": "ATR 72-500",
    "AT76": "ATR 72-600", "B06": "Bell 206", "B190": "Beech 1900", "B350": "King Air 350",
    "B37M": "737 MAX 7", "B38M": "737 MAX 8", "B39M": "737 MAX 9", "B3XM": "737 MAX 10",
    "B407": "Bell 407", "B412": "Bell 412", "B429": "Bell 429", "B505": "Bell 505",
    "B712": "717-200", "B733": "737-300", "B734": "737-400", "B737": "737-700", "B738": "737-800",
    "B739": "737-900", "B744": "747-400", "B748": "747-8", "B752": "757-200", "B753": "757-300",
    "B762": "767-200", "B763": "767-300", "B764": "767-400", "B772": "777-200", "B773": "777-300",
    "B778": "777-8", "B779": "777-9", "B77L": "777-200LR", "B77W": "777-300ER", "B788": "787-8",
    "B789": "787-9", "B78X": "787-10", "BCS1": "A220-100", "BCS3": "A220-300",
    "BE20": "King Air 200", "BE33": "Bonanza 33", "BE35": "Bonanza V35", "BE36": "Bonanza A36",
    "BE40": "Beechjet 400", "BE55": "Baron 55", "BE58": "Baron 58", "BE9L": "King Air 90",
    "C130": "C-130 Hercules", "C150": "Cessna 150", "C152": "Cessna 152", "C17": "C-17",
    "C172": "Cessna 172", "C177": "Cessna Cardinal", "C182": "Cessna 182", "C206": "Cessna 206",
    "C208": "Cessna Caravan", "C210": "Cessna 210", "C25A": "Citation CJ2", "C25B": "Citation CJ3",
    "C25C": "Citation CJ4", "C295": "C-295", "C30J": "C-130J Hercules", "C310": "Cessna 310",
    "C340": "Cessna 340", "C510": "Citation Mustang", "C525": "CitationJet",
    "C56X": "Citation Excel", "C5M": "C-5M Galaxy", "C680": "Cit. Sovereign",
    "C68A": "Cit. Latitude", "C700": "Cit. Longitude", "C750": "Citation X", "C919": "COMAC C919",
    "CL30": "Challenger 300", "CL35": "Challenger 350", "CL60": "Challenger 600",
    "CRJ2": "CRJ-200", "CRJ7": "CRJ-700", "CRJ9": "CRJ-900", "CRJX": "CRJ-1000",
    "D328": "Dornier 328", "DA40": "Diamond DA40", "DA42": "Diamond DA42", "DA62": "Diamond DA62",
    "DC10": "DC-10", "DC3": "DC-3", "DH8C": "Dash 8-300", "DH8D": "Dash 8 Q400",
    "DHC6": "Twin Otter", "E135": "ERJ-135", "E145": "ERJ-145", "E170": "E170", "E190": "E190",
    "E195": "E195", "E290": "E190-E2", "E295": "E195-E2", "E3CF": "E-3 Sentry",
    "E50P": "Phenom 100", "E55P": "Phenom 300", "E75L": "E175", "E75S": "E175", "EC20": "EC120",
    "EC30": "H130", "EC35": "H135", "EC45": "H145", "EXPL": "MD Explorer", "F100": "Fokker 100",
    "F2TH": "Falcon 2000", "F50": "Fokker 50", "F900": "Falcon 900", "FA7X": "Falcon 7X",
    "FA8X": "Falcon 8X", "G280": "Gulfstream G280", "GL5T": "Global 5000", "GL7T": "Global 7500",
    "GLEX": "Global Express", "GLF4": "Gulfstream IV", "GLF5": "Gulfstream V",
    "GLF6": "Gulfstream G650", "H160": "H160", "H25B": "Hawker 800", "H47": "CH-47 Chinook",
    "H500": "MD 500", "H60": "UH-60 Black Hawk", "H64": "AH-64 Apache", "HDJT": "HondaJet",
    "IL76": "Il-76", "JS41": "Jetstream 41", "K35R": "KC-135 Tanker", "LJ35": "Learjet 35",
    "LJ45": "Learjet 45", "LJ60": "Learjet 60", "LJ75": "Learjet 75", "M20P": "Mooney M20",
    "MD11": "MD-11", "MD82": "MD-82", "MD83": "MD-83", "MD88": "MD-88", "MD90": "MD-90",
    "P28A": "Piper Cherokee", "P28R": "Cherokee Arrow", "P8": "P-8 Poseidon", "PA18": "Super Cub",
    "PA32": "Piper PA-32", "PA34": "Piper Seneca", "PA44": "Piper Seminole",
    "PA46": "Piper Malibu", "PC12": "Pilatus PC-12", "PC24": "Pilatus PC-24",
    "R22": "Robinson R22", "R44": "Robinson R44", "R66": "Robinson R66", "S22T": "Cirrus SR22T",
    "S76": "Sikorsky S-76", "SB20": "Saab 2000", "SF34": "Saab 340", "SF50": "Vision Jet",
    "SR20": "Cirrus SR20", "SR22": "Cirrus SR22", "SU95": "Superjet 100", "TBM9": "TBM 900",
    "V22": "V-22 Osprey",
}

# IATA code: (city, latitude, longitude)
AIRPORTS = {
    "ADD": ("Addis Ababa", 8.9779, 38.7993),
    "AKL": ("Auckland", -37.0082, 174.7850),
    "AMS": ("Amsterdam", 52.3105, 4.7683),
    "ARN": ("Stockholm", 59.6485, 17.9288),
    "ATL": ("Atlanta", 33.6407, -84.4277),
    "AUH": ("Abu Dhabi", 24.4330, 54.6511),
    "AUS": ("Austin", 30.1945, -97.6699),
    "BCN": ("Barcelona", 41.2974, 2.0833),
    "BKK": ("Bangkok", 13.6900, 100.7501),
    "BOG": ("Bogota", 4.7016, -74.1469),
    "BOM": ("Mumbai", 19.0896, 72.8656),
    "BOS": ("Boston", 42.3656, -71.0096),
    "CAI": ("Cairo", 30.1115, 31.3967),
    "CDG": ("Paris", 49.0097, 2.5479),
    "CLT": ("Charlotte", 35.2140, -80.9431),
    "CPH": ("Copenhagen", 55.6180, 12.6508),
    "DCA": ("Washington", 38.8512, -77.0402),
    "DEL": ("Delhi", 28.5562, 77.1000),
    "DEN": ("Denver", 39.8561, -104.6737),
    "DFW": ("Dallas", 32.8998, -97.0403),
    "DOH": ("Doha", 25.2731, 51.6081),
    "DTW": ("Detroit", 42.2124, -83.3534),
    "DUB": ("Dublin", 53.4213, -6.2701),
    "DXB": ("Dubai", 25.2532, 55.3657),
    "EWR": ("Newark", 40.6895, -74.1745),
    "EZE": ("Buenos Aires", -34.8222, -58.5358),
    "FCO": ("Rome", 41.8045, 12.2520),
    "FLL": ("Fort Lauderdale", 26.0726, -80.1527),
    "FRA": ("Frankfurt", 50.0267, 8.5584),
    "GRU": ("Sao Paulo", -23.4356, -46.4731),
    "HKG": ("Hong Kong", 22.3080, 113.9185),
    "HND": ("Tokyo", 35.5494, 139.7798),
    "HNL": ("Honolulu", 21.3187, -157.9225),
    "IAD": ("Washington", 38.9531, -77.4565),
    "IAH": ("Houston", 29.9902, -95.3368),
    "ICN": ("Seoul", 37.4691, 126.4510),
    "IST": ("Istanbul", 41.2749, 28.7321),
    "JFK": ("New York", 40.6413, -73.7781),
    "JNB": ("Johannesburg", -26.1392, 28.2460),
    "KUL": ("Kuala Lumpur", 2.7456, 101.7072),
    "LAS": ("Las Vegas", 36.0840, -115.1537),
    "LAX": ("Los Angeles", 33.9416, -118.4085),
    "LGA": ("New York", 40.7769, -73.8740),
    "LHR": ("London", 51.4700, -0.4543),
    "LIS": ("Lisbon", 38.7742, -9.1342),
    "MAD": ("Madrid", 40.4983, -3.5676),
    "MCO": ("Orlando", 28.4312, -81.3081),
    "MEL": ("Melbourne", -37.6690, 144.8410),
    "MEX": ("Mexico City", 19.4361, -99.0719),
    "MIA": ("Miami", 25.7959, -80.2870),
    "MSP": ("Minneapolis", 44.8848, -93.2223),
    "MUC": ("Munich", 48.3538, 11.7861),
    "NRT": ("Tokyo", 35.7720, 140.3929),
    "OAK": ("Oakland", 37.7213, -122.2208),
    "ORD": ("Chicago", 41.9742, -87.9073),
    "PDX": ("Portland", 45.5898, -122.5951),
    "PEK": ("Beijing", 40.0799, 116.6031),
    "PHL": ("Philadelphia", 39.8744, -75.2424),
    "PHX": ("Phoenix", 33.4352, -112.0101),
    "PVG": ("Shanghai", 31.1443, 121.8083),
    "SAN": ("San Diego", 32.7338, -117.1933),
    "SCL": ("Santiago", -33.3930, -70.7858),
    "SEA": ("Seattle", 47.4502, -122.3088),
    "SFO": ("San Francisco", 37.6213, -122.3790),
    "SIN": ("Singapore", 1.3502, 103.9940),
    "SJC": ("San Jose", 37.3626, -121.9291),
    "SLC": ("Salt Lake City", 40.7899, -111.9791),
    "SYD": ("Sydney", -33.9399, 151.1753),
    "TPE": ("Taipei", 25.0777, 121.2328),
    "YUL": ("Montreal", 45.4706, -73.7408),
    "YVR": ("Vancouver", 49.1967, -123.1815),
    "YYZ": ("Toronto", 43.6777, -79.6248),
    "ZRH": ("Zurich", 47.4647, 8.5492),
}

# Helicopters and tiltrotors: glyph 2.
ROTORCRAFT = (
    "A109", "A119", "A139", "A149", "A169", "AS32", "AS50", "AS55", "AS65", "B06", "B06T", "B212",
    "B222", "B407", "B412", "B429", "B47G", "B505", "EC20", "EC25", "EC30", "EC35", "EC45", "EC55",
    "EN28", "EXPL", "H160", "H47", "H500", "H60", "H64", "MD52", "R22", "R44", "R66", "S61", "S76",
    "S92", "V22",
)

# Common light piston and single-turboprop types: glyph 1.
LIGHT = (
    "AA1", "AA5", "AC11", "BE19", "BE23", "BE33", "BE35", "BE36", "BE55", "BE58", "BE76", "C150",
    "C152", "C162", "C170", "C172", "C177", "C180", "C182", "C185", "C206", "C207", "C208", "C210",
    "C310", "C340", "C402", "C414", "C421", "COL4", "DA40", "DA42", "DA62", "DV20", "EPIC", "M20P",
    "M20T", "P28A", "P28B", "P28R", "P28T", "P46T", "PA18", "PA22", "PA24", "PA27", "PA31", "PA32",
    "PA34", "PA38", "PA44", "PA46", "PC12", "RV6", "RV7", "RV8", "S22T", "SIRA", "SR20", "SR22",
    "TB20", "TBM7", "TBM8", "TBM9",
)

# ---- Aircraft classes: what the Show filter sorts by --------------------------------------
AIRLINER, HEAVY, MIL, SMALL, OTHER = range(5)
ALL = 31                        # a mask with every class set: one bit per class

# key, Setup label, class mask, help strip. Order is the order B steps through.
SHOWS = (
    ("all", "All aircraft", ALL, "Every aircraft in range"),
    ("big", "Big only", (1 << AIRLINER) | (1 << HEAVY) | (1 << MIL), "Airliners, heavies and military"),
    ("airliner", "Airliners only", (1 << AIRLINER) | (1 << HEAVY), "Airliners and heavies, no military"),
    ("heavy", "Heavies only", 1 << HEAVY, "Wide-bodies: A350, 777, 787, A380, 747"),
    ("mil", "Military only", 1 << MIL, "Aircraft flagged military in the feed"),
    ("small", "Small only", 1 << SMALL, "Light planes, helicopters, business jets"),
)

# ICAO type designators the emitter category cannot place. Each string starts and ends with a
# space and has one between codes, so " B738 " is found by `in` and "B73" cannot match by accident.
# _SMALL holds the large-cabin business jets, which send A3 or A5 like an airliner, and the
# most common small types, for reports that carry no category.
_AIRLINER = (
    " A19N A20N A21N A318 A319 A320 A321 AT43 AT45 AT46 AT72 AT75 AT76 B37M B38M "
    "B39M B3XM B712 B732 B733 B734 B735 B736 B737 B738 B739 B752 B753 BCS1 BCS3 "
    "CRJ1 CRJ2 CRJ7 CRJ9 CRJX DH8A DH8B DH8C DH8D E120 E135 E145 E170 E190 E195 "
    "E290 E295 E45X E75L E75S F100 MD82 MD83 MD88 MD90 SB20 SF34 "
)
_HEAVY = (
    " A124 A306 A30B A310 A332 A333 A337 A338 A339 A342 A343 A345 A346 A359 A35K "
    "A388 B741 B742 B743 B744 B748 B762 B763 B764 B772 B773 B778 B779 B77L B77W "
    "B788 B789 B78X DC10 IL96 MD11 "
)
_SMALL = (
    " AS50 B350 B407 BE20 C150 C152 C172 C182 C208 C56X C68A C700 CL30 CL35 CL60 "
    "DA40 E545 E55P EC35 EC45 F2TH F900 FA7X FA8X G280 GA5C GA6C GA7C GA8C GL5T "
    "GL6T GL7T GLEX GLF4 GLF5 GLF6 M20P P208 P28A P32R PA31 PA44 PC12 R44 S22T "
    "SLG2 SR20 SR22 "
)


def classify(t, cat, flags, cs):
    """Class of an aircraft from its ICAO type, emitter category, dbFlags and callsign.

    The first rule that matches wins: not an aircraft, military flag, type table,
    emitter category, callsign shape. cat must be a string, "" when unknown.
    """
    if cat[:1] == "C" or t in ("TWR", "GND", "SERV"):
        return OTHER                    # surface vehicle, tower or obstacle
    if flags & 1:
        return MIL
    if t:
        k = " " + t + " "
        if k in _AIRLINER:
            return AIRLINER
        if k in _HEAVY:
            return HEAVY
        if k in _SMALL:
            return SMALL
    if cat == "A5":
        return HEAVY
    if cat == "A3" or cat == "A4":
        return AIRLINER
    if cat == "B6" or cat == "B7":
        return OTHER                    # a drone or a spacecraft; after the tables, a C182 once sent B6
    if cat in ("A1", "A2", "A6", "A7") or cat[:1] == "B":
        return SMALL
    if len(cs) > 3 and cs[:3].isalpha() and cs[3].isdigit():
        return AIRLINER                 # no category: an airline-style callsign such as UAL123
    return SMALL if cs or t else OTHER


def show_info(key):
    """The SHOWS entry with this key, else None."""
    for t in SHOWS:
        if t[0] == key:
            return t
    return None


def carrier_name(prefix):
    """Airline name for an ICAO callsign prefix; the prefix itself when AIRLINES does not know it."""
    hit = AIRLINES.get(prefix)
    return hit[0] if hit else prefix


def airline(callsign):
    """(prefix, name, IATA, colour) for an airline callsign such as UAL1234, else None."""
    if len(callsign) >= 4 and callsign[:3].isalpha() and callsign[3].isdigit():
        prefix = callsign[:3]
        hit = AIRLINES.get(prefix)
        if hit:
            return (prefix,) + hit
        if prefix in MILITARY:
            return (prefix, "Military", "", MIL_COLOUR)
        return (prefix, "", "", None)
    return None


def type_name(code):
    return TYPES.get(code, code)


def glyph(ac_type, category):
    """Glyph index for skyui.plane: 0 airliner, 1 light aircraft, 2 rotorcraft."""
    if category == "A7" or ac_type in ROTORCRAFT:
        return 2
    if category in ("A1", "B1", "B4") or ac_type in LIGHT:
        return 1
    return 0
