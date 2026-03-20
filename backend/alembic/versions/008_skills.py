"""Add skills and skill_submissions tables

Revision ID: 008_skills
Revises: 007_improvements
Create Date: 2026-03-20

What this migration does
─────────────────────────
Creates the two tables that back the Skills page:

  skills
    - Full metadata mirror of what SkillDB stores (PostgreSQL side of the
      dual-storage pattern; ChromaDB holds the embedded content).
    - description column included (Fix 11) so the popular-skills endpoint
      can return description without a ChromaDB round-trip.
    - Composite index on (verification_status, usage_count DESC) for the
      fast popular-skills query (Fix 22).
    - Index on creator_id for the "My Submissions" filter (Fix 4).

  skill_submissions
    - Pending skill submissions awaiting Council review.
    - FK to skills.skill_id with ON DELETE CASCADE.

All columns are nullable or have server defaults so this migration is
safe to run against a live database without downtime.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = '008_skills'
down_revision = '007_improvements'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    print("🚀 Starting migration 008_skills ...")

    # =========================================================================
    # skills
    # =========================================================================
    if 'skills' not in existing_tables:
        op.create_table(
            'skills',
            # BaseEntity columns (mirrors base.py)
            sa.Column('id',          sa.String(36),  primary_key=True),
            sa.Column('is_active',   sa.Boolean(),   nullable=False, server_default='true'),
            sa.Column('created_at',  sa.DateTime(),  nullable=False,
                      server_default=sa.text('NOW()')),
            sa.Column('updated_at',  sa.DateTime(),  nullable=False,
                      server_default=sa.text('NOW()')),
            sa.Column('deleted_at',  sa.DateTime(),  nullable=True),

            # Identity
            sa.Column('skill_id',     sa.String(50),  nullable=False),
            sa.Column('skill_name',   sa.String(100), nullable=False),
            sa.Column('display_name', sa.String(200), nullable=False),
            # Fix 11 — description cached here so to_dict() can include it
            # without an extra ChromaDB call (used by PopularSkillCard).
            sa.Column('description',  sa.String(300), nullable=True),

            # Categorisation
            sa.Column('skill_type',  sa.String(50), nullable=False),
            sa.Column('domain',      sa.String(50), nullable=False),
            sa.Column('tags',        sa.JSON(),     nullable=False, server_default='[]'),
            sa.Column('complexity',  sa.String(20), nullable=False),

            # ChromaDB reference
            sa.Column('chroma_id',         sa.String(100), nullable=False),
            sa.Column('chroma_collection', sa.String(50),  nullable=False,
                      server_default='agent_skills'),
            sa.Column('embedding_model',   sa.String(100), nullable=False,
                      server_default='sentence-transformers/all-MiniLM-L6-v2'),

            # Provenance
            sa.Column('creator_tier',    sa.String(20),  nullable=False),
            sa.Column('creator_id',      sa.String(20),  nullable=False),
            sa.Column('parent_skill_id', sa.String(50),  nullable=True),
            sa.Column('task_origin',     sa.String(50),  nullable=True),

            # Quality metrics
            sa.Column('success_rate',    sa.Float(),   nullable=False, server_default='0.0'),
            sa.Column('usage_count',     sa.Integer(), nullable=False, server_default='0'),
            sa.Column('retrieval_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_retrieved',  sa.DateTime(), nullable=True),

            # Governance
            sa.Column('constitution_compliant', sa.Boolean(),    nullable=False, server_default='false'),
            sa.Column('verification_status',    sa.String(20),   nullable=False, server_default='pending'),
            sa.Column('verified_by',            sa.String(20),   nullable=True),
            sa.Column('verified_at',            sa.DateTime(),   nullable=True),
            sa.Column('rejection_reason',       sa.String(500),  nullable=True),
        )

        # Unique lookup by skill_id
        op.create_index(
            'ix_skills_skill_id',
            'skills', ['skill_id'],
            unique=True,
        )

        # Fix 22 — composite index for the popular-skills query:
        #   WHERE verification_status = 'verified' ORDER BY usage_count DESC
        # A full table scan without this index degrades on every page load.
        op.create_index(
            'ix_skills_verification_usage',
            'skills', ['verification_status', 'usage_count'],
        )

        # Fix 4 — index for creator_id so "My Submissions" post-filter is fast
        op.create_index(
            'ix_skills_creator_id',
            'skills', ['creator_id'],
        )

        # Composite index for domain-filtered popular queries
        op.create_index(
            'ix_skills_domain_usage',
            'skills', ['domain', 'verification_status', 'usage_count'],
        )

        print("  ✅ Created skills table")
    else:
        # Table already exists — ensure the description column is present
        # (may be missing on instances that created the table before Fix 11).
        existing_cols = {
            col['name'] for col in inspector.get_columns('skills')
        }
        if 'description' not in existing_cols:
            op.add_column(
                'skills',
                sa.Column('description', sa.String(300), nullable=True),
            )
            print("  ✅ Added description column to existing skills table")
        else:
            print("  ℹ️  skills already exists — skipping creation")

    # =========================================================================
    # skill_submissions
    # =========================================================================
    if 'skill_submissions' not in existing_tables:
        op.create_table(
            'skill_submissions',
            # BaseEntity columns
            sa.Column('id',         sa.String(36),  primary_key=True),
            sa.Column('is_active',  sa.Boolean(),   nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(),  nullable=False,
                      server_default=sa.text('NOW()')),
            sa.Column('updated_at', sa.DateTime(),  nullable=False,
                      server_default=sa.text('NOW()')),
            sa.Column('deleted_at', sa.DateTime(),  nullable=True),

            sa.Column('submission_id', sa.String(50), nullable=False),
            sa.Column(
                'skill_id',
                sa.String(50),
                sa.ForeignKey('skills.skill_id', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('submitted_by', sa.String(20),   nullable=False),
            sa.Column('submitted_at', sa.DateTime(),   nullable=True,
                      server_default=sa.text('NOW()')),

            # Review fields
            sa.Column('status',           sa.String(20),   nullable=False, server_default='pending'),
            sa.Column('council_vote_id',  sa.String(50),   nullable=True),
            sa.Column('reviewed_by',      sa.String(20),   nullable=True),
            sa.Column('reviewed_at',      sa.DateTime(),   nullable=True),
            sa.Column('review_notes',     sa.String(1000), nullable=True),

            # Full skill data snapshot for reviewer display
            sa.Column('skill_data', sa.JSON(), nullable=False, server_default='{}'),
        )

        op.create_index(
            'ix_skill_submissions_submission_id',
            'skill_submissions', ['submission_id'],
            unique=True,
        )
        op.create_index(
            'ix_skill_submissions_skill_id',
            'skill_submissions', ['skill_id'],
        )
        op.create_index(
            'ix_skill_submissions_status',
            'skill_submissions', ['status'],
        )
        op.create_index(
            'ix_skill_submissions_submitted_by',
            'skill_submissions', ['submitted_by'],
        )

        print("  ✅ Created skill_submissions table")
    else:
        print("  ℹ️  skill_submissions already exists — skipping creation")

    print("\n" + "=" * 60)
    print("✅ Migration 008_skills completed!")
    print("=" * 60)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    print("🔄 Downgrading migration 008_skills ...")

    if 'skill_submissions' in existing_tables:
        op.drop_index('ix_skill_submissions_submitted_by',  table_name='skill_submissions')
        op.drop_index('ix_skill_submissions_status',        table_name='skill_submissions')
        op.drop_index('ix_skill_submissions_skill_id',      table_name='skill_submissions')
        op.drop_index('ix_skill_submissions_submission_id', table_name='skill_submissions')
        op.drop_table('skill_submissions')
        print("  ✅ Dropped skill_submissions")

    if 'skills' in existing_tables:
        op.drop_index('ix_skills_domain_usage',          table_name='skills')
        op.drop_index('ix_skills_creator_id',            table_name='skills')
        op.drop_index('ix_skills_verification_usage',    table_name='skills')
        op.drop_index('ix_skills_skill_id',              table_name='skills')
        op.drop_table('skills')
        print("  ✅ Dropped skills")

    print("✅ Downgrade 008_skills completed.")