"""Add (or update) the official service categories and skills.

Run from the backend folder (venv active), after create_tables.py:
    python seed_skills.py

Safe to run again: it only adds or fixes what is missing, and it keeps the ids of
categories and skills that already exist, so provider profiles are not affected.
"""

from app.database import SessionLocal
from app.models import Category, Skill

# Old category names from Step 4 -> new names (renamed in place, ids are kept)
RENAMES = {
    "Home & Cleaning": "Home Cleaning",
    "Tutoring": "Tutor",
    "Beauty & Mehendi": "Beautician",
}

CATALOG = {
    "Electrician": [
        "Electrical Wiring",
        "Fan & Light Installation",
        "Inverter & Battery Service",
        "Switchboard Repair",
    ],
    "Plumber": [
        "Leak Repair",
        "Pipe Fitting",
        "Bathroom Fitting",
        "Water Tank Cleaning",
    ],
    "Tutor": [
        "Home Tuition",
        "Maths & Science Tutor",
        "Spoken English",
        "Music Lessons",
    ],
    "Carpenter": [
        "Furniture Repair",
        "Custom Furniture",
        "Door & Window Fitting",
        "Modular Kitchen Work",
    ],
    "Beautician": [
        "Mehendi",
        "Bridal Makeup",
        "Hair Styling",
        "Facial & Waxing",
        "Manicure & Pedicure",
    ],
    "Mechanic": [
        "Bike Mechanic",
        "Car Mechanic",
        "AC & Refrigerator Repair",
        "Washing Machine Repair",
    ],
    "Photographer": [
        "Event Photography",
        "Wedding Photography",
        "Portrait Photography",
        "Videography",
    ],
    "Designer": [
        "Graphic Design",
        "Interior Design",
        "Fashion Design",
        "Web Design",
    ],
    "Home Cleaning": [
        "House Cleaning",
        "Deep Cleaning",
        "Sofa & Carpet Cleaning",
        "Daily Helper",
        "Home Assistance",
    ],
    "Computer Repair": [
        "Laptop Repair",
        "Desktop Repair",
        "Software & OS Installation",
        "Data Recovery",
        "WiFi & Network Setup",
    ],
    # Core SkillConnect services (kept from Step 4)
    "Cooking & Food": ["Home Cook", "Tiffin Service", "Baking", "Catering Help"],
    "Childcare & Elder Care": ["Babysitting", "Nanny", "Elder Care"],
    "Tailoring & Handicrafts": [
        "Tailoring",
        "Embroidery",
        "Knitting & Crochet",
        "Handicrafts",
    ],
    "Other": ["Other Local Service"],
}


def main():
    db = SessionLocal()
    try:
        renamed = new_categories = new_skills = moved = 0

        # 1. Rename old categories in place (only if the new name is not taken yet)
        for old_name, new_name in RENAMES.items():
            old = db.query(Category).filter(Category.name == old_name).first()
            taken = db.query(Category).filter(Category.name == new_name).first()
            if old is not None and taken is None:
                old.name = new_name
                renamed += 1
        db.flush()

        # 2. Add missing categories and skills
        for category_name, skill_names in CATALOG.items():
            category = db.query(Category).filter(Category.name == category_name).first()
            if category is None:
                category = Category(name=category_name)
                db.add(category)
                db.flush()  # gives the new category an id
                new_categories += 1
            for skill_name in skill_names:
                skill = db.query(Skill).filter(Skill.name == skill_name).first()
                if skill is None:
                    db.add(Skill(category_id=category.id, name=skill_name))
                    new_skills += 1
                elif skill.category_id != category.id or skill.created_by_id is not None:
                    # the official list wins: put it in the right category, mark official
                    skill.category_id = category.id
                    skill.created_by_id = None
                    moved += 1
        db.commit()

        print(f"Renamed {renamed} categories.")
        print(f"Added {new_categories} categories and {new_skills} skills.")
        if moved:
            print(f"Moved/updated {moved} existing skills.")
        print(
            f"The database now has {db.query(Category).count()} categories "
            f"and {db.query(Skill).count()} skills."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
