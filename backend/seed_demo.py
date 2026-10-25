"""Add demo data (providers, customers, reviews) so the project looks alive in a demo.

Run from the backend folder (venv active), after create_tables.py and seed_skills.py:
    python seed_demo.py                 # add demo data
    python seed_demo.py --city Pune     # use another city (default: Mumbai)
    python seed_demo.py --remove        # delete all demo data again

All demo accounts use the email pattern  demo.<name>@example.com  and ONE password
that you type when the script asks (it is never stored in a file).
Safe to run twice: existing demo accounts are skipped.
"""

import argparse
import getpass
import sys
from datetime import datetime, time, timedelta

from app.database import SessionLocal
from app.models import (
    Availability, Location, Message, ProviderProfile, ProviderSkill, RequestServiceMode,
    RequestStatus, Review, ServiceRequest, ServiceMode, Skill, User, UserRole, WeekDay,
)
from app.schemas import check_password_strength
from app.security import hash_password

DEMO_LIKE = "demo.%@example.com"
DEMO_LIKE_ESCAPE = "!"

PROVIDERS = [
    ("Rahul Sharma", "electrician", ["Electrical Wiring", "Fan & Light Installation"], 8, "Experienced electrician for homes and shops.", "Rs 300 per visit"),
    ("Anita Verma", "tutor", ["Home Tuition", "Maths & Science Tutor"], 5, "Maths and science tutor for classes 6 to 10.", "Rs 400 per hour"),
    ("Imran Khan", "plumber", ["Leak Repair", "Pipe Fitting"], 10, "Quick leak repair and bathroom fittings.", "Rs 350 per visit"),
    ("Pooja Patil", "beautician", ["Mehendi", "Hair Styling"], 4, "Mehendi and hair styling at your home.", "From Rs 500"),
    ("Suresh Nair", "carpenter", ["Furniture Repair", "Door & Window Fitting"], 12, "Furniture repair and door fitting.", "Rs 600 per day"),
]
CUSTOMERS = ["Meera Singh", "Karan Gupta", "Neha Joshi"]
REVIEWS = [
    (5, "Very professional and on time. Highly recommended."),
    (4, "Good work, fair price."),
    (5, "Excellent service, will book again."),
]


def email_for(name: str) -> str:
    return "demo." + name.lower().replace(" ", ".") + "@example.com"


def ask_password() -> str:
    while True:
        first = getpass.getpass("Choose ONE password for all demo accounts: ")
        try:
            check_password_strength(first, None)
        except ValueError as error:
            print("  Not strong enough:", error)
            continue
        if getpass.getpass("Type it again: ") != first:
            print("  The two passwords do not match.")
            continue
        return first


def get_location(db, city, area):
    loc = db.query(Location).filter(Location.city == city, Location.area == area, Location.pincode.is_(None)).first()
    if not loc:
        loc = Location(city=city, area=area)
        db.add(loc)
        db.flush()
    return loc


def remove_demo(db):
    ids = [u.id for u in db.query(User).filter(User.email.like(DEMO_LIKE, escape=DEMO_LIKE_ESCAPE)).all()]
    if not ids:
        print("No demo data found.")
        return
    db.query(ServiceRequest).filter((ServiceRequest.customer_id.in_(ids)) | (ServiceRequest.provider_id.in_(ids))).delete(synchronize_session=False)
    db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    print(f"Removed {len(ids)} demo account(s) and their requests.")


def add_user(db, name, role, password, loc):
    email = email_for(name)
    if db.query(User).filter(User.email == email).first():
        print(f"  skip (exists): {email}")
        return None
    user = User(full_name=name, email=email, password_hash=hash_password(password), role=role, location_id=loc.id)
    db.add(user)
    db.flush()
    print(f"  added {role.value.lower()}: {email}")
    return user


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="Mumbai")
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.remove:
            remove_demo(db)
            return
        skills = {s.name: s for s in db.query(Skill).all()}
        if not skills:
            sys.exit("No skills found. Run: python seed_skills.py")
        password = ask_password()
        areas = ["Andheri", "Bandra", "Dadar", "Borivali", "Thane"]
        providers = []
        for index, (name, _kind, skill_names, years, about, price) in enumerate(PROVIDERS):
            loc = get_location(db, args.city, areas[index % len(areas)])
            user = add_user(db, name, UserRole.PROVIDER, password, loc)
            if user is None:
                providers.append(db.query(User).filter(User.email == email_for(name)).first())
                continue
            profile = ProviderProfile(user_id=user.id, description=about, experience_years=years, service_mode=ServiceMode.BOTH,
                                      pricing_info=price, working_area=f"{args.city} and nearby", qualification="Verified demo provider")
            db.add(profile)
            db.flush()
            for sname in skill_names:
                if sname in skills:
                    db.add(ProviderSkill(provider_profile_id=profile.id, skill_id=skills[sname].id))
            for day in (WeekDay.MONDAY, WeekDay.TUESDAY, WeekDay.WEDNESDAY, WeekDay.THURSDAY, WeekDay.FRIDAY, WeekDay.SATURDAY):
                db.add(Availability(provider_profile_id=profile.id, day_of_week=day, start_time=time(9, 0), end_time=time(18, 0)))
            providers.append(user)
        customers = []
        for index, name in enumerate(CUSTOMERS):
            loc = get_location(db, args.city, areas[index % len(areas)])
            user = add_user(db, name, UserRole.CUSTOMER, password, loc)
            customers.append(user or db.query(User).filter(User.email == email_for(name)).first())

        # Completed jobs with reviews, so ratings show up on the provider pages
        made = 0
        for p_index, provider in enumerate(providers):
            first_skill = db.query(ProviderSkill).join(ProviderProfile).filter(ProviderProfile.user_id == provider.id).first()
            if first_skill is None:
                continue
            for c_index, customer in enumerate(customers):
                exists = db.query(ServiceRequest).filter(ServiceRequest.customer_id == customer.id, ServiceRequest.provider_id == provider.id).first()
                if exists or (p_index + c_index) % 4 == 3:
                    continue
                when = datetime.now() - timedelta(days=7 + c_index * 3)
                req = ServiceRequest(customer_id=customer.id, provider_id=provider.id, skill_id=first_skill.skill_id,
                                     location_id=customer.location_id, service_mode=RequestServiceMode.NON_REGULAR,
                                     scheduled_at=when, duration_hours=2, message="Demo job (completed).",
                                     status=RequestStatus.COMPLETED)
                db.add(req)
                db.flush()
                rating, comment = REVIEWS[(p_index + c_index) % len(REVIEWS)]
                db.add(Review(service_request_id=req.id, reviewer_id=customer.id, provider_id=provider.id, rating=rating, comment=comment))
                made += 1
        # One pending request with a chat message, for the live demo
        if providers and customers:
            first_skill = db.query(ProviderSkill).join(ProviderProfile).filter(ProviderProfile.user_id == providers[0].id).first()
            pending = db.query(ServiceRequest).filter(ServiceRequest.customer_id == customers[0].id, ServiceRequest.provider_id == providers[0].id,
                                                      ServiceRequest.status == RequestStatus.PENDING).first()
            if first_skill and not pending:
                req = ServiceRequest(customer_id=customers[0].id, provider_id=providers[0].id, skill_id=first_skill.skill_id,
                                     location_id=customers[0].location_id, service_mode=RequestServiceMode.NON_REGULAR,
                                     scheduled_at=datetime.now() + timedelta(days=2), duration_hours=2,
                                     message="Two fans and one switchboard need fixing.", status=RequestStatus.PENDING)
                db.add(req)
                db.flush()
                db.add(Message(service_request_id=req.id, sender_id=customers[0].id, body="Hello! Are you free the day after tomorrow morning?"))
        db.commit()
        print(f"\nDone. {made} completed job(s) with reviews added.")
        print("Log in with any  demo.<first>.<last>@example.com  address, e.g. " + email_for(PROVIDERS[0][0]))
        print("Remove everything later with:  python seed_demo.py --remove")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
