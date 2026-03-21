"""Supabase migration to add Qwilr columns to agency_proposals and create proposal_events."""
import sys

MIGRATION_SQL = """
-- =============================================================================
-- Migration: Add Qwilr integration to existing agency_proposals table
-- =============================================================================

-- Add Qwilr columns to existing agency_proposals table
-- (safe to run multiple times — IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)

ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS client_contact VARCHAR(255);
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS client_email VARCHAR(255);
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS proposal_data JSONB DEFAULT '{}'::jsonb;
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS valid_until DATE;

-- Qwilr integration columns
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS qwilr_page_id VARCHAR(100);
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS qwilr_url TEXT;
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS qwilr_share_url TEXT;
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS qwilr_status VARCHAR(50) DEFAULT 'draft';

-- Tracking columns
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS first_viewed_at TIMESTAMPTZ;
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS last_viewed_at TIMESTAMPTZ;
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS view_count INTEGER DEFAULT 0;
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ;
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS accepted_by VARCHAR(255);

-- Investment tracking
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS selected_tier VARCHAR(50);
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS selected_amount DECIMAL(12, 2);

-- Lifecycle
ALTER TABLE agency_proposals ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Indexes for Qwilr lookups
CREATE INDEX IF NOT EXISTS idx_agency_proposals_qwilr_page_id
    ON agency_proposals(qwilr_page_id);
CREATE INDEX IF NOT EXISTS idx_agency_proposals_qwilr_status
    ON agency_proposals(qwilr_status);

-- Proposal events audit log (uses proposal_id VARCHAR to match agency_proposals)
CREATE TABLE IF NOT EXISTS proposal_events (
    id              SERIAL PRIMARY KEY,
    proposal_id     VARCHAR(50) NOT NULL,
    event_type      VARCHAR(50) NOT NULL,
    event_data      JSONB DEFAULT '{}'::jsonb,
    source          VARCHAR(50) DEFAULT 'qwilr',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proposal_events_proposal
    ON proposal_events(proposal_id);
CREATE INDEX IF NOT EXISTS idx_proposal_events_type
    ON proposal_events(event_type);

-- Enable RLS on new table
ALTER TABLE proposal_events ENABLE ROW LEVEL SECURITY;

-- Service role policy for proposal_events
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'proposal_events'
        AND policyname = 'Service role full access on proposal_events'
    ) THEN
        CREATE POLICY "Service role full access on proposal_events"
            ON proposal_events FOR ALL
            USING (true)
            WITH CHECK (true);
    END IF;
END $$;
"""


def main():
    """Print the migration SQL for use in Supabase SQL Editor."""
    if "--print" in sys.argv or len(sys.argv) == 1:
        print(MIGRATION_SQL)
        print("\\n-- Copy this SQL and run it in the Supabase SQL Editor")
        print("-- This extends your existing agency_proposals table (non-destructive)")
    else:
        print("Usage: python scripts/migrate_supabase.py [--print]")
        print("\\nCopy the output and run it in your Supabase SQL Editor.")


if __name__ == "__main__":
    main()
