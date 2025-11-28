import random

# Lists of common Indian first and last names (expanded)
first_names = [
    "Amit", "Priya", "Raj", "Anjali", "Vikram", "Kavita", "Arjun", "Meera",
    "Suresh", "Sunita", "Rahul", "Neha", "Ravi", "Pooja", "Karan", "Sneha",
    "Aman", "Divya", "Rohit", "Kriti", "Vivek", "Alisha", "Nikhil", "Sakshi",
    "Deepak", "Ananya", "Mohit", "Isha", "Gaurav", "Riya", "Sandeep", "Tanya",
    "Abhishek", "Anushka", "Arvind", "Bhavna", "Chetan", "Disha", "Esha", "Farhan",
    "Geeta", "Harish", "Indira", "Jatin", "Kiran", "Lakshmi", "Manish", "Nandini",
    "Om", "Pankaj", "Qamar", "Radha", "Sanjay", "Tanvi", "Umesh", "Vaishali",
    "Waseem", "Yamini", "Zara"
]

last_names = [
    "Sharma", "Patel", "Singh", "Kumar", "Gupta", "Jain", "Verma", "Chopra",
    "Nair", "Reddy", "Yadav", "Shah", "Joshi", "Mehta", "Agarwal", "Bhat",
    "Rao", "Iyer", "Pillai", "Das", "Chatterjee", "Banerjee", "Mukherjee", "Saha",
    "Thakur", "Malhotra", "Kapoor", "Saxena", "Mishra", "Tiwari", "Pandey", "Dubey",
    "Kulkarni", "Deshmukh", "Patil", "Sawant", "Naik", "Gaikwad", "Bhosale", "Jadhav",
    "Shetty", "Rao", "Murthy", "Nambiar", "Menon", "Pillai", "Kurian", "Thomas"
]

# Lists of Indian cities and states with codes (expanded)
city_state = {
    "Mumbai": "MH", "Delhi": "DL", "Bangalore": "KA", "Chennai": "TN",
    "Kolkata": "WB", "Hyderabad": "TS", "Pune": "MH", "Ahmedabad": "GJ",
    "Jaipur": "RJ", "Surat": "GJ", "Lucknow": "UP", "Kanpur": "UP",
    "Nagpur": "MH", "Indore": "MP", "Thane": "MH", "Bhopal": "MP",
    "Visakhapatnam": "AP", "Pimpri-Chinchwad": "MH", "Patna": "BR", "Vadodara": "GJ",
    "Gurugram": "HR", "Chandigarh": "CH", "Panchkula": "HR", "Noida": "UP",
    "Ghaziabad": "UP", "Faridabad": "HR", "Ludhiana": "PB", "Amritsar": "PB",
    "Jalandhar": "PB", "Patiala": "PB", "Bathinda": "PB", "Hoshiarpur": "PB",
    "Mohali": "PB", "Zirakpur": "PB", "Kharar": "PB", "Rajpura": "PB",
    "Sangrur": "PB", "Barnala": "PB", "Firozpur": "PB", "Kapurthala": "PB",
    "Moga": "PB", "Sri Muktsar Sahib": "PB", "Tarn Taran": "PB", "Pathankot": "PB",
    "Gurdaspur": "PB", "Batala": "PB", "Dhuri": "PB", "Malerkotla": "PB",
    "Khanna": "PB", "Phillaur": "PB", "Nakodar": "PB", "Shahabad": "PB",
    "Raikot": "PB", "Jagraon": "PB", "Sunam": "PB", "Lehra Gaga": "PB",
    "Raman": "PB", "Talwandi Sabo": "PB", "Budhlada": "PB", "Maur": "PB",
    "Dhanaula": "PB", "Sardulgarh": "PB", "Bhikhi": "PB", "Rania": "PB",
    "Sultanpur Lodhi": "PB", "Sham Chaurasi": "PB", "Begowal": "PB", "Rahon": "PB",
    "Nabha": "PB", "Bhawanigarh": "PB", "Samana": "PB", "Pehowa": "PB",
    "Kalanaur": "PB", "Gohana": "PB", "Sonipat": "HR", "Panipat": "HR",
    "Karnal": "HR", "Hisar": "HR", "Rohtak": "HR", "Bhiwani": "HR",
    "Sirsa": "HR", "Fatehabad": "HR", "Jind": "HR", "Kaithal": "HR",
    "Kurukshetra": "HR", "Yamunanagar": "HR", "Ambala": "HR", "Rewari": "HR",
    "Mahendragarh": "HR", "Jhajjar": "HR", "Palwal": "HR", "Charkhi Dadri": "HR",
    "Nuh": "HR", "Hathin": "HR", "Loharu": "HR", "Chhachhrauli": "HR",
    "Shahabad": "HR", "Pehowa": "HR", "Indri": "HR", "Gharaunda": "HR",
    "Assandh": "HR", "Safidon": "HR", "Ratia": "HR", "Fatehabad": "HR",
    "Tohana": "HR", "Jakhal": "HR", "Narwana": "HR", "Uchana": "HR",
    "Barwala": "HR", "Dabwali": "HR", "Ellenabad": "HR", "Narnaund": "HR",
    "Adampur": "HR", "Uklana": "HR", "Bhattu": "HR", "Kalayat": "HR",
    "Ladwa": "HR", "Pipli": "HR", "Israna": "HR", "Gohana": "HR",
    "Samalkha": "HR", "Ganaur": "HR", "Kharkhoda": "HR", "Bahadurgarh": "HR",
    "Badli": "HR", "Jhajjar": "HR", "Beri": "HR", "Ateli": "HR",
    "Narnaul": "HR", "Mandhan": "HR", "Kosli": "HR", "Jatusana": "HR",
    "Uchana": "HR", "Fatehabad": "HR", "Ratia": "HR", "Jakhal": "HR",
    "Tohana": "HR", "Narwana": "HR", "Uchana": "HR", "Barwala": "HR",
    "Dabwali": "HR", "Ellenabad": "HR", "Narnaund": "HR", "Adampur": "HR",
    "Uklana": "HR", "Bhattu": "HR", "Kalayat": "HR", "Ladwa": "HR",
    "Pipli": "HR", "Israna": "HR", "Gohana": "HR", "Samalkha": "HR",
    "Ganaur": "HR", "Kharkhoda": "HR", "Bahadurgarh": "HR", "Badli": "HR",
    "Jhajjar": "HR", "Beri": "HR", "Ateli": "HR", "Narnaul": "HR",
    "Mandhan": "HR", "Kosli": "HR", "Jatusana": "HR"
}

cities = list(city_state.keys())

# Apartment names (expanded)
apartments = [
    "Bharat Apartment", "Shanti Nagar", "Green Valley", "Royal Residency",
    "Sunshine Towers", "Lake View", "Garden Estate", "City Plaza", "Metro Heights",
    "Sunrise Enclave", "Crystal Towers", "Golden Palm Heights", "Silver Oaks Residency",
    "Aangan Greens", "Horizon Towers", "Royal Residency", "Nilaya Villas",
    "Emerald Palm", "Oasis Greens", "Golden Sands", "Silver Moon", "Green Horizon",
    "Imperial Towers", "Sankalp Residency", "Skyline Apartments", "Palm Grove",
    "Crystal Clear", "Golden Gate", "Silver Star", "Green Meadows", "Royal Gardens",
    "Nilaya Heights", "Aangan Villas", "Horizon Greens", "Sunset Towers"
]

# Areas/Localities (expanded)
areas = [
    "Jayanagar", "Sainikpuri", "Koramangala", "Indiranagar", "Rajajinagar",
    "Whitefield", "Electronic City", "HSR Layout", "Marathahalli", "BTM Layout",
    "Malleshwaram", "Basavanagudi", "Frazer Town", "Richmond Town",
    "Connaught Place", "Karol Bagh", "Janakpuri", "Malviya Nagar", "Saket", "Rohini",
    "Dwarka Sector 10", "Bandra West", "Andheri East", "Juhu", "Powai", "Dadar",
    "Chembur", "Borivali West", "T. Nagar", "Adyar", "Anna Nagar", "Besant Nagar",
    "Velachery", "Pallikaranai", "Mylapore", "Salt Lake", "Ballygunge", "New Town",
    "Shibpur", "Behala", "Dum Dum", "Sector 15", "Block A", "Phase II",
    "Kirti Nagar", "MG Road GPO", "SBI Bank", "Sai Baba Temple", "Phoenix Mall",
    "City Police Station", "Central Mall"
]

# Street names (expanded with Hindi terms)
streets = [
    "5th Cross Road", "5th Main Road", "1st Main Road", "2nd Cross Street",
    "MG Road", "Park Street", "Church Street", "Station Road", "Market Road",
    "Ring Road", "Mall Road", "Bazaar Street", "Lane 1", "Avenue Road",
    "Mahatma Gandhi Marg", "Jawaharlal Nehru Road", "Netaji Subhash Sarani",
    "Rose Lane", "Peacock Path", "1st Cross", "12th Main", "Gandhi Gali",
    "Nehru Path", "Subhash Chowk", "Lily Sarani", "Parrot Nagara", "Temple Kovil",
    "Bank Sadak", "School Veedhi", "Hospital Marg", "Park Gali", "Market Chowk",
    "Station Sarani", "Church Path", "Mall Nagara"
]

def generate_random_name():
    first_name = random.choice(first_names)
    last_name = random.choice(last_names)
    return f"{first_name} {last_name}"

def generate_random_address():
    # Randomly decide if to include apartment
    has_apartment = random.choice([True, False])

    # Generate house number (sometimes with / like 4-158/9 or 44/1)
    if random.choice([True, False]):
        house_number = f"{random.randint(1, 999)}-{random.randint(1, 999)}/{random.randint(1, 9)}"
    else:
        house_number = f"{random.randint(1, 999)}/{random.randint(1, 9)}"

    # Apartment if applicable
    apartment = ""
    if has_apartment:
        apartment = f"{random.choice(apartments)}\n"

    # Street
    street = random.choice(streets)

    # Area
    area = random.choice(areas)

    # City and state
    city = random.choice(cities)
    state_code = city_state[city]

    # Pincode
    pincode = random.randint(100000, 999999)

    # Format address
    address = f"{house_number}\n{apartment}{street}\n{area}\n{city} {pincode}, {state_code}\nIND"
    return address

if __name__ == "__main__":
    name = generate_random_name()
    address = generate_random_address()
    print()
    print(f"{name}")
    print(f"{address}")
    print()
    print("Please come again...")
