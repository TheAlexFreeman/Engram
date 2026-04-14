#!/bin/bash

set -euo pipefail

# =============================================================================
# Setup Cloudflare R2 Buckets
# =============================================================================
# Creates three R2 buckets:
#   - better-base-backups       (private, no CORS)
#   - better-base-prod-public   (public, with CORS)
#   - better-base-prod-private  (private, with CORS)
#
# Requires environment variables:
# * DevOps_Server_Setup_TODO: Set `CLOUDFLARE_SETUP_API_KEY` in the environment.
#   - `CLOUDFLARE_SETUP_API_KEY` - API token with R2 and Memberships (and whatever else)
#     permissions.
# * DevOps_Server_Setup_TODO: Set `CLOUDFLARE_ACCOUNT_ID` in the environment.
#   - `CLOUDFLARE_ACCOUNT_ID` - Account ID (to skip account selection prompt).
# * DevOps_Server_Setup_TODO: Set `CLOUDFLARE_ZONE_ID` in the environment.
#   - `CLOUDFLARE_ZONE_ID` - Zone ID for betterbase.com (for custom domain setup).
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Delay between API calls to avoid rate limiting (in seconds). Cloudflare's rate limits
# can be strict.
API_DELAY=${API_DELAY:-1.2}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Validation
# =============================================================================

validate_env_vars() {
    if [[ -z "${CLOUDFLARE_SETUP_API_KEY:-}" ]]; then
        log_error "\`CLOUDFLARE_SETUP_API_KEY\` environment variable is not set."
        exit 1
    fi

    if [[ ${#CLOUDFLARE_SETUP_API_KEY} -lt 10 ]]; then
        log_error "\`CLOUDFLARE_SETUP_API_KEY\` must be at least 10 characters long."
        exit 1
    fi

    if [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
        log_error "\`CLOUDFLARE_ACCOUNT_ID\` environment variable is not set."
        log_error "This is your account ID (find it in Cloudflare dashboard, skips account selection)."
        exit 1
    fi

    if [[ ${#CLOUDFLARE_ACCOUNT_ID} -lt 6 ]]; then
        log_error "\`CLOUDFLARE_ACCOUNT_ID\` must be at least 6 characters long."
        log_error "This is your account ID (find it in Cloudflare dashboard, skips account selection)."
        exit 1
    fi

    if [[ -z "${CLOUDFLARE_ZONE_ID:-}" ]]; then
        log_error "\`CLOUDFLARE_ZONE_ID\` environment variable is not set."
        log_error "This is the zone ID for betterbase.com (find it in Cloudflare dashboard)."
        exit 1
    fi

    if [[ ${#CLOUDFLARE_ZONE_ID} -lt 6 ]]; then
        log_error "\`CLOUDFLARE_ZONE_ID\` must be at least 6 characters long."
        log_error "This is the zone ID for betterbase.com (find it in Cloudflare dashboard)."
        exit 1
    fi

    log_info "Environment variable validation passed."
}

# =============================================================================
# Bucket Creation
# =============================================================================

create_buckets() {
    local CLOUDFLARE_API_TOKEN="$CLOUDFLARE_SETUP_API_KEY"
    export CLOUDFLARE_API_TOKEN
    export CLOUDFLARE_ACCOUNT_ID
    export CLOUDFLARE_ZONE_ID

    log_info "Creating R2 buckets..."

    # Create better-base-backups (private, no CORS)
    log_info "Creating bucket: better-base-backups"
    if bunx wrangler r2 bucket create better-base-backups 2>/dev/null; then
        log_info "Bucket 'better-base-backups' created successfully."
    else
        log_warn "Bucket 'better-base-backups' may already exist or failed to create."
    fi
    sleep "$API_DELAY"

    # Create better-base-prod-public (will be made public)
    log_info "Creating bucket: better-base-prod-public"
    if bunx wrangler r2 bucket create better-base-prod-public 2>/dev/null; then
        log_info "Bucket 'better-base-prod-public' created successfully."
    else
        log_warn "Bucket 'better-base-prod-public' may already exist or failed to create."
    fi
    sleep "$API_DELAY"

    # Create better-base-prod-private (private with CORS)
    log_info "Creating bucket: better-base-prod-private"
    if bunx wrangler r2 bucket create better-base-prod-private 2>/dev/null; then
        log_info "Bucket 'better-base-prod-private' created successfully."
    else
        log_warn "Bucket 'better-base-prod-private' may already exist or failed to create."
    fi
    sleep "$API_DELAY"
}

# =============================================================================
# Public Access Configuration
# =============================================================================

configure_public_access() {
    local CLOUDFLARE_API_TOKEN="$CLOUDFLARE_SETUP_API_KEY"
    export CLOUDFLARE_API_TOKEN
    export CLOUDFLARE_ACCOUNT_ID
    export CLOUDFLARE_ZONE_ID

    # Disable the r2.dev URL (we use a custom domain instead).
    log_info "Disabling r2.dev URL for better-base-prod-public..."
    if bunx wrangler r2 bucket dev-url disable better-base-prod-public --force 2>/dev/null; then
        log_info "r2.dev URL disabled for 'better-base-prod-public'."
    else
        log_warn "Failed to disable r2.dev URL or it may already be disabled."
    fi
    sleep "$API_DELAY"

    # Add custom domain files.betterbase.com to the public bucket.
    log_info "Adding custom domain files.betterbase.com to better-base-prod-public..."
    if bunx wrangler r2 bucket domain add better-base-prod-public \
        --domain files.betterbase.com \
        --zone-id "$CLOUDFLARE_ZONE_ID" \
        --force 2>/dev/null; then
        log_info "Custom domain 'files.betterbase.com' added to 'better-base-prod-public'."
    else
        log_warn "Failed to add custom domain or it may already be configured."
    fi
    sleep "$API_DELAY"
}

# =============================================================================
# CORS Configuration
# =============================================================================

configure_cors() {
    local CLOUDFLARE_API_TOKEN="$CLOUDFLARE_SETUP_API_KEY"
    export CLOUDFLARE_API_TOKEN
    export CLOUDFLARE_ACCOUNT_ID
    export CLOUDFLARE_ZONE_ID

    log_info "Configuring CORS policies..."

    # Create a temporary file for the CORS configuration.
    local cors_file
    cors_file=$(mktemp)

    # This CORS policy applies to both `prod-public` and `prod-private` buckets.
    # Wrangler expects nested format with lowercase field names.
    cat > "$cors_file" << 'EOF'
{
  "rules": [
    {
      "allowed": {
        "origins": [
          "https://betterbase.com",
          "https://app.betterbase.com",
          "https://demo.betterbase.com",
          "https://files.betterbase.com",
          "https://www.betterbase.com"
        ],
        "methods": ["GET", "HEAD"],
        "headers": ["*"]
      },
      "exposeHeaders": [
        "Age",
        "Cache-Control",
        "Content-Disposition",
        "Content-Encoding",
        "Content-Length",
        "Date",
        "ETag",
        "Last-Modified",
        "Vary"
      ],
      "maxAgeSeconds": 3600
    }
  ]
}
EOF

    # Apply CORS to `better-base-prod-public`.
    log_info "Applying CORS policy to better-base-prod-public..."
    if bunx wrangler r2 bucket cors set better-base-prod-public --file "$cors_file" --force; then
        log_info "CORS policy applied to 'better-base-prod-public'."
    else
        log_error "Failed to apply CORS policy to 'better-base-prod-public'."
    fi
    sleep "$API_DELAY"

    # Apply CORS to `better-base-prod-private`.
    log_info "Applying CORS policy to better-base-prod-private..."
    if bunx wrangler r2 bucket cors set better-base-prod-private --file "$cors_file" --force; then
        log_info "CORS policy applied to 'better-base-prod-private'."
    else
        log_error "Failed to apply CORS policy to 'better-base-prod-private'."
    fi
    sleep "$API_DELAY"

    # Clean up the temporary file.
    rm -f "$cors_file"

    log_info "CORS configuration complete."
}

# =============================================================================
# Verification
# =============================================================================

verify_setup() {
    local CLOUDFLARE_API_TOKEN="$CLOUDFLARE_SETUP_API_KEY"
    export CLOUDFLARE_API_TOKEN
    export CLOUDFLARE_ACCOUNT_ID
    export CLOUDFLARE_ZONE_ID

    log_info "Verifying bucket setup..."

    echo ""
    log_info "Listing all R2 buckets:"
    bunx wrangler r2 bucket list
    sleep "$API_DELAY"

    echo ""
    log_info "CORS policy for better-base-prod-public:"
    bunx wrangler r2 bucket cors list better-base-prod-public || true
    sleep "$API_DELAY"

    echo ""
    log_info "CORS policy for better-base-prod-private:"
    bunx wrangler r2 bucket cors list better-base-prod-private || true
}

# =============================================================================
# Main
# =============================================================================

main() {
    log_info "Starting Cloudflare R2 bucket setup..."
    echo ""

    validate_env_vars
    create_buckets
    configure_public_access
    configure_cors
    verify_setup

    echo ""
    log_info "Cloudflare R2 bucket setup complete!"
    echo ""
    echo "Summary:"
    echo "  - better-base-backups:      Private (no public access, no CORS)"
    echo "  - better-base-prod-public:  Public (files.betterbase.com, CORS configured)"
    echo "  - better-base-prod-private: Private (no public access, CORS configured)"
    echo ""
    echo "Note: Ensure DNS for files.betterbase.com is configured correctly in Cloudflare."
}

main "$@"
