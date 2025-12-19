import pandas as pd

# ============================================================
# Load enriched 100-sample
# ============================================================

df = pd.read_csv("../evaluation/sample-for-annotation-400-2.csv")
df.columns = df.columns.str.lower()


# ============================================================
# Helper functions
# ============================================================

def norm(s):
    if pd.isna(s):
        return ""
    return str(s).strip().lower()

def is_true(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "y", "yes", "true", "t"}


# ============================================================
# Zsolt's rules
# ============================================================

BAD_CARGO = {"produce", "meat", "livestock", "garbage"}
GOOD_PACKAGE_KEYWORDS = {"package delivery", "parcel", "courier"}
GOOD_RESTORATION_KEYWORDS = {"restoration"}
BAD_USDOT_STATUS = {"inactive", "out of service", "out-of-service", "out_of_service"}

def zsolt_label(row):

    cargo = norm(row.get("cargo_carried", ""))
    carrier_op = norm(row.get("carrier_operation", ""))
    usdot_status = norm(row.get("usdot_status", ""))
    hm = is_true(row.get("hm_flag") or row.get("hazmat") or row.get("hazmat_flag"))
    authorized = is_true(row.get("authorized_for_hire"))
    intrastate_flag = is_true(row.get("intrastate"))
    interstate_flag = is_true(row.get("interstate"))
    name = norm(row.get("company_name"))
    desc = norm(row.get("description"))
    combined = f"{name} {desc} {cargo}"

    # ---- DEFINITIVE BAD ----

    if usdot_status in BAD_USDOT_STATUS:
        return "BAD"

    if carrier_op == "b" and hm:
        return "BAD"

    if is_true(row.get("private_passenger_business")) or is_true(row.get("private_passenger_nonbusiness")):
        return "BAD"
    
    if is_true(row.get("pc_flag")):
        return "BAD"

    if any(bad in cargo for bad in BAD_CARGO):
        return "BAD"

    # ---- OK RULE ----
    
    is_intrastate = intrastate_flag

    missing_cargo = cargo == ""

    if authorized and is_intrastate and not hm and missing_cargo:
        return "OK"

    # ---- DEFINITIVE GOOD ----

    is_interstate = interstate_flag or carrier_op == "a"
    if is_interstate and "general freight" in cargo:
        return "GOOD"

    if any(k in combined for k in GOOD_PACKAGE_KEYWORDS) or ("amazon" in combined and "delivery" in combined):
        return "GOOD"

    if any(k in combined for k in GOOD_RESTORATION_KEYWORDS):
        return "GOOD"

    # ---- DEFAULT OPEN CATEGORY ----

    return "OK"


# ============================================================
# Apply the rule classifier
# ============================================================

df["rule_granular"] = df.apply(zsolt_label, axis=1)
df["rule_binary"] = df["rule_granular"].map(
    {"BAD": "BAD", "OK": "GOOD", "GOOD": "GOOD", "GREAT": "GOOD"}
)

df["expert_label"] = df["expert_label"].astype(str).str.strip().str.upper()
df["expert_binary"] = df["expert_label"].map(
    {"BAD": "BAD", "OK": "GOOD", "GOOD": "GOOD", "GREAT": "GOOD"}
)


# ============================================================
# Zsolt wants ONLY: expert GOOD → rule BAD flips
# ============================================================

df["needs_flip"] = (df["expert_binary"] == "GOOD") & (df["rule_binary"] == "BAD")


# ============================================================
# Add reason for GOOD→BAD flips only
# ============================================================

def flip_reason(row):
    if not row["needs_flip"]:
        return ""

    cargo = norm(row.get("cargo_carried", ""))
    carrier_op = norm(row.get("carrier_operation", ""))
    usdot_status = norm(row.get("usdot_status", ""))
    hm = is_true(row.get("hm_flag") or row.get("hazmat") or row.get("hazmat_flag"))
    name = norm(row.get("company_name"))
    desc = norm(row.get("description"))
    combined = f"{name} {desc} {cargo}"

    # --- BAD rules causing flip ---

    if usdot_status in BAD_USDOT_STATUS:
        return "DOT inactive/out-of-service → BAD"
    
    if is_true(row.get("pc_flag")):
        return "Passenger carrier (pc_flag) → BAD"

    if carrier_op == "b" and hm:
        return "Intrastate (B) + HM → BAD"
    
    if is_true(row.get("private_passenger_business")) or is_true(row.get("private_passenger_nonbusiness")):
        return "Private passenger (business or nonbusiness) → BAD"
    
    if is_true(row.get("pc_flag")):
        return "Passenger carrier (pc_flag) → BAD"
        
    if any(b in cargo for b in BAD_CARGO):
        return "BAD cargo type (produce/meat/livestock/garbage) → BAD"

    return "Rule-Based BAD (default BAD conditions triggered)"


df["flip_reason"] = df.apply(flip_reason, axis=1)


# ============================================================
# Save only GOOD→BAD flips
# ============================================================

df_flips = df[df["needs_flip"]].copy()

output_path = "../evaluation/previous_batch_good_to_bad_flips-400-2.csv"
df_flips.to_csv(output_path, index=False)

print("✓ Script complete.")
print(f"✓ {len(df_flips)} GOOD→BAD flips detected.")
print(f"✓ Saved to: {output_path}")
