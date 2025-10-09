import dns.resolver
import polars as pl


def validate_email_domains(email_series: pl.Series) -> pl.Series:
    """
    Given a Polars Series of email addresses, return a Boolean Series
    indicating whether the email’s domain resolves (via MX or A record).
    """

    resolver = dns.resolver.Resolver()
    resolver.timeout = 2
    resolver.lifetime = 3

    cache = {}

    def domain_is_valid(domain: str) -> bool:
        if not domain:
            return False
        if domain in cache:
            return cache[domain]
        try:
            resolver.resolve(domain, "MX")
            cache[domain] = True
        except dns.resolver.NoAnswer:
            try:
                resolver.resolve(domain, "A")
                cache[domain] = True
            except Exception:
                cache[domain] = False
        except (
            dns.resolver.NXDOMAIN,
            dns.resolver.LifetimeTimeout,
            dns.resolver.NoNameservers,
            dns.resolver.NoMetaqueries,
        ):
            cache[domain] = False
        except Exception:
            cache[domain] = False
        return cache[domain]

    domains = email_series.str.extract(r"@([\w\.-]+)$").str.to_lowercase()

    results = [domain_is_valid(d) for d in domains]
    return pl.Series(results, dtype=pl.Boolean)


if __name__ == "__main__":
    INPUT_FILE = "./data/SMS_Input_-_Motor_Carrier_Census_Information_20250919.parquet"
    EMAIL_COLUMN = "EMAIL_ADDRESS"
    SAMPLE_SIZE = 100

    print(f"📂 Reading: {INPUT_FILE}")
    df = pl.read_parquet(INPUT_FILE)

    if EMAIL_COLUMN not in df.columns:
        raise ValueError(f"Column '{EMAIL_COLUMN}' not found")

    # Sample 100 random emails
    n = len(df)
    sample_n = min(SAMPLE_SIZE, n)
    df_sample = df.sample(n=sample_n, seed=42)
    print(f"🎯 Sampled {sample_n} emails")

    # Validate domains
    valids = validate_email_domains(df_sample[EMAIL_COLUMN])
    df_sample = df_sample.with_columns(valids.alias("domain_valid"))

    # Summary
    valid_count = df_sample["domain_valid"].sum()
    invalid_count = sample_n - valid_count
    valid_pct = 100 * valid_count / sample_n

    print("\n📊 Domain Validity Report")
    print("-------------------------")
    print(f"Total checked: {sample_n}")
    print(f"✅ Valid domains: {valid_count} ({valid_pct:.1f}%)")
    print(f"❌ Invalid emails/domains: {invalid_count} ({100 - valid_pct:.1f}%)")
    print("\n🧾 Sample results:")
    print(
        df_sample.select(
            ["DOT_NUMBER", "LEGAL_NAME", "EMAIL_ADDRESS", "domain_valid"]
        ).head(10)
    )
