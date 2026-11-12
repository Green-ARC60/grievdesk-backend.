"""
GrievDesk Demo Data Seeder
Populates a complete, realistic dataset to demonstrate all 12 edge cases,
roles, workflows, amenities, dues, and announcements.
"""

import sys
import os
from datetime import datetime, date, time, timedelta, timezone

from app import create_app
from app.extensions import db
from app.models.user import User, Role, ApprovalStatus
from app.models.complaint import Complaint, ComplaintCategory, Severity, ComplaintStatus
from app.models.service_request import ServiceRequest, ServiceType
from app.models.announcement import Announcement
from app.models.due import Due, PaidStatus
from app.models.amenity import Amenity, AmenityBooking, BookingStatus
from app.models.bylaws_document import BylawsDocument
from app.models.ticket_event import TicketEvent

app = create_app()

def seed():
    with app.app_context():
        print("--- Seeding GrievDesk Demo Dataset ---")

        # 1. Secretary
        secretary = db.session.query(User).filter_by(role=Role.SECRETARY).first()
        if not secretary:
            secretary = User(
                name="Ramesh Patel",
                gmail="secretary56@gmail.com",
                phone="+91 9876543210",
                flat_no="424",
                block_no="A",
                preferred_language="en",
                role=Role.SECRETARY,
                approval_status=ApprovalStatus.APPROVED,
                share_phone=True
            )
            secretary.set_password("Password123!")
            db.session.add(secretary)
            db.session.flush()
            print(f"Created Secretary: {secretary.name} ({secretary.gmail})")
        else:
            print(f"Secretary exists: {secretary.name} ({secretary.gmail})")

        # 2. Committee Member
        committee = db.session.query(User).filter_by(gmail="vikram.committee@grievdesk.org").first()
        if not committee:
            committee = User(
                name="Vikram Joshi",
                gmail="vikram.committee@grievdesk.org",
                phone="+91 9876543211",
                flat_no="201",
                block_no="A",
                preferred_language="en",
                role=Role.COMMITTEE,
                approval_status=ApprovalStatus.APPROVED,
                share_phone=True
            )
            committee.set_password("Password123!")
            db.session.add(committee)
            db.session.flush()
            print(f"Created Committee Member: {committee.name}")

        # 3. Approved Residents
        residents_data = [
            ("Aakash Sharma", "aakash.sharma@example.com", "+91 9811122233", "202", "B", "hi", True),
            ("Sunita Mohanty", "sunita.mohanty@example.com", "+91 9822233344", "301", "B", "or", False), # Private phone
            ("Karthik Subramanian", "karthik.s@example.com", "+91 9833344455", "405", "C", "ta", True),
        ]
        
        residents = []
        for name, email, phone, flat, block, lang, share in residents_data:
            u = db.session.query(User).filter_by(gmail=email).first()
            if not u:
                u = User(
                    name=name,
                    gmail=email,
                    phone=phone,
                    flat_no=flat,
                    block_no=block,
                    preferred_language=lang,
                    role=Role.RESIDENT,
                    approval_status=ApprovalStatus.APPROVED,
                    share_phone=share
                )
                u.set_password("Password123!")
                db.session.add(u)
                db.session.flush()
                print(f"Created Resident: {name} (Flat {flat}, Block {block}, Lang: {lang})")
            residents.append(u)

        # 4. Pending Resident (For Edge Case 9 Demo)
        pending_user = db.session.query(User).filter_by(gmail="ananya.deshmukh@example.com").first()
        if not pending_user:
            pending_user = User(
                name="Ananya Deshmukh",
                gmail="ananya.deshmukh@example.com",
                phone="+91 9844455566",
                flat_no="104",
                block_no="A",
                preferred_language="mr",
                role=Role.RESIDENT,
                approval_status=ApprovalStatus.PENDING,
                share_phone=False
            )
            pending_user.set_password("Password123!")
            db.session.add(pending_user)
            db.session.flush()
            print(f"Created Pending Resident for Approval Queue: {pending_user.name}")

        # 5. Society Rulebook (Version 1)
        if not db.session.query(BylawsDocument).first():
            bylaws = BylawsDocument(
                version=1,
                uploaded_by=secretary.id,
                content_text="""GREEN VALLEY COOPERATIVE HOUSING SOCIETY - BYLAWS 2026

Section 1: General Code of Conduct & Quiet Hours
1.1 Strict quiet hours are observed between 10:00 PM and 7:00 AM daily.
1.2 Loud music, party speakers, drill machines, and construction work are strictly forbidden during quiet hours.

Section 2: Designated Parking & Vehicle Regulations
2.1 Each flat is allocated exactly one numbered basement parking slot.
2.2 Visitor vehicles may only park in designated visitor slots for at most 6 hours with prior security gate approval.
2.3 Electric vehicle (EV) charging is only permitted at the designated society charging bays.

Section 3: Pet Etiquette & Animal Guidelines
3.1 Domestic pets (dogs and cats) are welcome in the society.
3.2 All pets must be kept on a leash in common areas, elevators, and corridors.
3.3 Owners are strictly responsible for cleaning up any waste immediately.

Section 4: Waste Segregation & Collection
4.1 Wet and dry waste must be segregated before 8:00 AM daily door-to-door collection.
4.2 E-waste and hazardous materials must be deposited in the clubhouse collection bin.

Section 5: Amenity Bookings & Fees
5.1 The Clubhouse / Community Hall may be reserved for private resident events at Rs. 2,000 per 4-hour slot.
5.2 Badminton court and gym are free for residents; max booking duration is 2 hours per day.
"""
            )
            db.session.add(bylaws)
            print("Indexed Society Bylaws Document (Version 1)")

        # 6. Sample Complaints
        res_b = residents[0] # Aakash Sharma, Block B
        res_b2 = residents[1] # Sunita Mohanty, Block B
        res_c = residents[2] # Karthik, Block C

        existing_complaints = db.session.query(Complaint).count()
        if existing_complaints == 0:
            # Complaint 1: Primary issue in Block B
            c1 = Complaint(
                user_id=res_b.id,
                raw_text="Water leakage from hallway ceiling in block B near flat 202",
                translated_text="Severe water leakage from the corridor ceiling in Block B near flat 202, causing water to pool on the floor.",
                original_language="en",
                category=ComplaintCategory.PLUMBING,
                severity=Severity.HIGH,
                status=ComplaintStatus.IN_PROGRESS,
                is_anonymous=False
            )
            db.session.add(c1)
            db.session.flush()

            # Event timeline for C1
            db.session.add(TicketEvent(
                ticket_type="complaint", ticket_id=c1.id, actor_id=res_b.id,
                action="status_changed", detail="new", note="Complaint submitted by resident."
            ))
            db.session.add(TicketEvent(
                ticket_type="complaint", ticket_id=c1.id, actor_id=committee.id,
                action="status_changed", detail="in_progress", note="Status updated to In Progress. Plumber dispatched to inspect valve."
            ))

            # Complaint 2: Duplicate of C1 (Edge Case 3 Demo)
            c2 = Complaint(
                user_id=res_b2.id,
                raw_text="Water dripping heavily from ceiling in block B 3rd floor hallway",
                translated_text="Heavy water dripping from the ceiling corridor in Block B near the staircase.",
                original_language="en",
                category=ComplaintCategory.PLUMBING,
                severity=Severity.HIGH,
                status=ComplaintStatus.IN_PROGRESS,
                duplicate_of=c1.id,
                is_anonymous=False
            )
            db.session.add(c2)
            db.session.flush()
            db.session.add(TicketEvent(
                ticket_type="complaint", ticket_id=c2.id, actor_id=res_b2.id,
                action="linked", detail=f"#{c1.id}", note=f"Linked as duplicate of #{c1.id} (matching block B plumbing issue)."
            ))

            # Complaint 3: Escalated Ticket (Edge Case 7 Demo)
            stale_date = datetime.now(timezone.utc) - timedelta(days=6)
            c3 = Complaint(
                user_id=res_b.id,
                raw_text="Elevator B2 making loud grinding noise and shaking violently",
                translated_text="Elevator B2 is vibrating vigorously and emitting a loud mechanical grinding noise when moving between floors 2 and 4.",
                original_language="en",
                category=ComplaintCategory.ELECTRICAL,
                severity=Severity.HIGH,
                status=ComplaintStatus.ESCALATED,
                is_anonymous=False,
                created_at=stale_date
            )
            db.session.add(c3)
            db.session.flush()
            db.session.add(TicketEvent(
                ticket_type="complaint", ticket_id=c3.id, actor_id=secretary.id,
                action="status_changed", detail="escalated", note="Auto-escalated: ticket remained unacknowledged past the 5-day threshold."
            ))

            # Complaint 4: Anonymous Sensitive Ticket (Edge Case 6 Demo)
            c4 = Complaint(
                user_id=res_c.id,
                raw_text="Loud shouting and domestic disturbance near staircase Block C late at night",
                translated_text="Repeated loud arguments, screaming, and physical disturbance observed in Block C late at night around 1:00 AM.",
                original_language="en",
                category=ComplaintCategory.NOISE,
                severity=Severity.MEDIUM,
                status=ComplaintStatus.NEW,
                is_anonymous=True
            )
            db.session.add(c4)
            db.session.flush()
            db.session.add(TicketEvent(
                ticket_type="complaint", ticket_id=c4.id, actor_id=res_c.id,
                action="status_changed", detail="new", note="Anonymous complaint filed. Identity masked from public inbox."
            ))
            print("Seeded 4 realistic complaints (Normal, Duplicate, Escalated, and Anonymous).")

        # 7. Announcements
        if db.session.query(Announcement).count() == 0:
            a1 = Announcement(
                posted_by=secretary.id,
                title="Annual General Body Meeting (AGM) - Nov 15th",
                message="The Society Annual General Meeting (AGM) will be held on Sunday, Nov 15th at 10:30 AM in the Clubhouse Hall. Agenda includes annual financial audit review and election of new committee members. All homeowners are requested to attend.",
                is_pinned=True
            )
            a2 = Announcement(
                posted_by=committee.id,
                title="Overhead Water Tank Cleaning Notice",
                message="Water supply across Block A, B, and C will be temporarily suspended tomorrow (Saturday) from 10:00 AM to 1:00 PM for scheduled overhead tank maintenance and chlorination. Please store sufficient water.",
                is_pinned=False
            )
            db.session.add(a1)
            db.session.add(a2)
            print("Seeded 2 Announcements (1 Pinned, 1 General).")

        # 8. Monthly Dues
        if db.session.query(Due).count() == 0:
            month_str = "2026-11"
            due_date_val = date(2026, 11, 25)
            
            # Due 1: Paid by Flat 202
            d1 = Due(
                user_id=res_b.id,
                month=month_str,
                amount=2500.0,
                due_date=due_date_val,
                paid_status=PaidStatus.PAID,
                paid_at=datetime.now(timezone.utc)
            )
            # Due 2: Unpaid by Flat 301
            d2 = Due(
                user_id=res_b2.id,
                month=month_str,
                amount=2500.0,
                due_date=due_date_val,
                paid_status=PaidStatus.UNPAID
            )
            # Due 3: Unpaid by Flat 405
            d3 = Due(
                user_id=res_c.id,
                month=month_str,
                amount=2500.0,
                due_date=due_date_val,
                paid_status=PaidStatus.UNPAID
            )
            db.session.add(d1)
            db.session.add(d2)
            db.session.add(d3)
            print("Seeded Monthly Maintenance Dues records (Paid and Unpaid).")

        # 9. Amenities & Bookings
        if db.session.query(Amenity).count() == 0:
            am1 = Amenity(
                name="Clubhouse & Banquet Hall",
                description="Air-conditioned hall with seating for 120 guests, sound system, and pantry area."
            )
            am2 = Amenity(
                name="Badminton Court",
                description="Synthetic rubber-mat indoor court. Non-marking shoes mandatory."
            )
            am3 = Amenity(
                name="Swimming Pool & Gymnasium",
                description="Outdoor pool and fully equipped fitness center with cardio and weight machines."
            )
            db.session.add(am1)
            db.session.add(am2)
            db.session.add(am3)
            db.session.flush()

            # Sample Booking for tomorrow
            tomorrow = date.today() + timedelta(days=1)
            b1 = AmenityBooking(
                amenity_id=am1.id,
                user_id=res_b.id,
                date=tomorrow,
                start_time=time(18, 0),
                end_time=time(20, 0),
                status=BookingStatus.BOOKED
            )
            db.session.add(b1)
            print("Seeded Amenities and sample reservations.")

        db.session.commit()
        print("\n[SUCCESS] SEEDING COMPLETE! All demo records successfully inserted.")

if __name__ == "__main__":
    seed()
