from db.database_url import (
    asyncpg_connect_args,
    prefer_supabase_transaction_pooler,
    use_null_pool,
)


def test_rewrites_supabase_session_pooler_to_transaction_pooler():
    url = (
        "postgresql+asyncpg://postgres.abc:secret@"
        "aws-1-eu-central-1.pooler.supabase.com:5432/postgres?ssl=require"
    )
    assert prefer_supabase_transaction_pooler(url) == (
        "postgresql+asyncpg://postgres.abc:secret@"
        "aws-1-eu-central-1.pooler.supabase.com:6543/postgres?ssl=require"
    )


def test_leaves_local_database_url_unchanged():
    url = "postgresql+asyncpg://finance:pass@db:5432/finance_ai"
    assert prefer_supabase_transaction_pooler(url) == url


def test_supabase_pooler_uses_null_pool_and_disables_statement_cache():
    url = (
        "postgresql+asyncpg://postgres.abc:secret@"
        "aws-1-eu-central-1.pooler.supabase.com:6543/postgres?ssl=require"
    )
    assert use_null_pool(url) is True
    assert asyncpg_connect_args(url) == {
        "ssl": "require",
        "statement_cache_size": 0,
    }
