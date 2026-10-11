"""Add the starter service categories and skills.

Run from the backend folder (venv active), after create_tables.py:
    python seed_skills.py

Safe to run again: it only adds what is missing.
"""

from app.database import SessionLocal
from app.models import Category, Skill

CATALOG = {
    "Home & Cleaning": [
        "House Cleaning",
        "Deep Cleaning",
        "Daily Helper",
        "Home Assistance",
    ],
    "Cooking & Food": ["Home Cook", "Tiffin Service", "Baking", "Catering Help"],
    "Childcare & Elder Care": ["Babysitting", "Nanny", "Elder Care"],
    "Beauty & Mehendi": ["Mehendi", "Bridal Makeup", "Hair Styling", "Facial & Waxing"],
    "Tailoring & Handicrafts": [
        "Tailoring",
        "Embroidery",
        "Knitting & Crochet",
        "Handicrafts",
    ],
    "Tutoring": ["Home Tuition", "Spoken English", "Music Lessons"],
    "Other": ["Other Local Service"],
}


def main():
    db = SessionLocal()
    try:
        new_categories = 0
        new_skills = 0
        for category_name, skill_names in CATALOG.items():
            category = db.query(Category).filter(Category.name == category_name).first()
            if category is None:
                category = Category(name=category_name)
                db.add(category)
                db.flush()  # gives the new category an id
                new_categories += 1
            for skill_name in skill_names:
                exists = db.query(Skill).filter(Skill.name == skill_name).first()
                if exists is None:
                    db.add(Skill(category_id=category.id, name=skill_name))
                    new_skills += 1
        db.commit()
        total_skills = db.query(Skill).count()
        print(f"Added {new_categories} categories and {new_skills} skills.")
        print(f"The database now has {total_skills} skills in total.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
