#!/bin/bash
set -euo pipefail

# Growth Engine Pipeline — Full Run
# Usage:
#   ./run_pipeline.sh --source-dirs "dir1 dir2" [options]
#
# Required:
#   --source-dirs    Space-separated source_item directories
#
# Options:
#   --run-id         Run identifier (default: YYYYMMDD_HHMMSS)
#   --skip-review    Auto-select topics without human review
#   --approved-file  File with approved topic IDs (skips auto-select)
#   --dry-run        Stop before actual X publish
#   --account        Target account (default: xiaodao-ai-lab)
#   --max-inline     Max inline images per article (default: 3)
#   --skip-images    Skip image generation
#   --skip-publish   Skip publish step

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── Defaults ──────────────────────────────────────────────
RUN_ID="$(date +%Y%m%d_%H%M%S)"
SOURCE_DIRS=""
SKIP_REVIEW=false
APPROVED_FILE=""
DRY_RUN=false
ACCOUNT="xiaodao-ai-lab"
MAX_INLINE=3
SKIP_IMAGES=false
SKIP_PUBLISH=false
ENABLE_VALUE_ESTIMATE=false
BIT_API_PORT=54345

# ── Parse args ────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --source-dirs) SOURCE_DIRS="$2"; shift 2 ;;
        --run-id) RUN_ID="$2"; shift 2 ;;
        --skip-review) SKIP_REVIEW=true; shift ;;
        --approved-file) APPROVED_FILE="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --account) ACCOUNT="$2"; shift 2 ;;
        --max-inline) MAX_INLINE="$2"; shift 2 ;;
        --skip-images) SKIP_IMAGES=true; shift ;;
        --skip-publish) SKIP_PUBLISH=true; shift ;;
        --enable-value-estimate) ENABLE_VALUE_ESTIMATE=true; shift ;;
        --bit-api-port) BIT_API_PORT="$2"; shift 2 ;;
        --run-ingest) RUN_INGEST=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [ -z "$SOURCE_DIRS" ]; then
    echo "Error: --source-dirs required"
    echo "Usage: ./run_pipeline.sh --source-dirs 'path/to/sources1 path/to/sources2'"
    exit 1
fi

# ── Paths ─────────────────────────────────────────────────
RUN_ROOT="runtime/runs/${RUN_ID}"
ENGINE_OUT="${RUN_ROOT}/01_engine"
WRITER_OUT="${RUN_ROOT}/02_writer"
IMAGE_OUT="${RUN_ROOT}/03_images"
PUBLISH_OUT="${RUN_ROOT}/04_publish"

mkdir -p "$ENGINE_OUT" "$WRITER_OUT" "$IMAGE_OUT" "$PUBLISH_OUT"

echo "════════════════════════════════════════════"
echo "  Growth Engine Pipeline"
echo "  Run: ${RUN_ID}"
echo "  Sources: ${SOURCE_DIRS}"
echo "════════════════════════════════════════════"

# ── L0: INGEST (optional) ────────────────────────────────
# If --run-ingest is passed, run source acquisition first
if [ "${RUN_INGEST:-false}" = true ]; then
    echo ""
    echo "▶ L0: Source Acquisition"
    INGEST_OUT="${RUN_ROOT}/00_ingest"
    mkdir -p "${INGEST_OUT}/x/items" "${INGEST_OUT}/podcast/items"

    # X/Twitter RSS ingest
    if [ -f "pipeline/ingest/x/discover_official_x_guest_rss.py" ]; then
        python3 pipeline/ingest/x/discover_official_x_guest_rss.py \
            --out-dir "${INGEST_OUT}/x" 2>&1 | tail -3 || echo "  ⚠ X ingest failed"
    fi

    # Normalize source items
    if [ -f "pipeline/ingest/normalize.py" ]; then
        for raw_dir in "${INGEST_OUT}"/*/items; do
            python3 pipeline/ingest/normalize.py \
                --source-dir "$raw_dir" \
                --out-dir "$raw_dir" 2>&1 | tail -1 || true
        done
    fi

    # Add ingest output to source dirs
    for items_dir in "${INGEST_OUT}"/*/items; do
        if [ -d "$items_dir" ] && [ "$(ls -A "$items_dir" 2>/dev/null)" ]; then
            SOURCE_DIRS="$SOURCE_DIRS $items_dir"
        fi
    done
    echo "  ✓ Ingest complete, sources updated"
fi

# ── L1: TOPIC ENGINE ──────────────────────────────────────
echo ""
echo "▶ L1: Topic Engine"

SOURCE_ARGS=""
for dir in $SOURCE_DIRS; do
    SOURCE_ARGS="$SOURCE_ARGS --source-item-root $dir"
done

ENGINE_CMD="python3 pipeline/engine/topic_engine.py \
    $SOURCE_ARGS \
    --out-root $ENGINE_OUT"

if [ "$SKIP_REVIEW" = true ]; then
    ENGINE_CMD="$ENGINE_CMD --auto-select-topics"
fi
if [ -n "$APPROVED_FILE" ]; then
    ENGINE_CMD="$ENGINE_CMD --approved-topic-ids-file $APPROVED_FILE"
fi
if [ "$ENABLE_VALUE_ESTIMATE" = true ]; then
    ENGINE_CMD="$ENGINE_CMD --enable-value-estimate --value-model claude-haiku-4-5-20251001"
fi

eval $ENGINE_CMD
echo "  ✓ Topic engine complete"

# Check if review is needed
REVIEW_REQUIRED=$(python3 -c "
import json
m = json.load(open('${ENGINE_OUT}/topic_engine_manifest.json'))
print('true' if m.get('review_required', False) else 'false')
")

if [ "$REVIEW_REQUIRED" = "true" ]; then
    echo ""
    echo "════════════════════════════════════════════"
    echo "  REVIEW REQUIRED"
    echo "  选题清单: ${ENGINE_OUT}/topic_ranking.json"
    echo ""
    echo "  审核后运行:"
    echo "  ./run_pipeline.sh --source-dirs '$SOURCE_DIRS' \\"
    echo "    --run-id $RUN_ID \\"
    echo "    --approved-file approved_topics.json"
    echo "════════════════════════════════════════════"

    # Generate human-readable review list
    python3 -c "
import json
ranking = json.load(open('${ENGINE_OUT}/topic_ranking.json'))
rows = ranking.get('ranking', [])
print()
for i, row in enumerate(rows, 1):
    valid = 'Y' if row['valid_for_pool'] else 'N'
    tier = row['quality_tier']
    lane = row['selected_lane_id']
    score = row['ranking_score']
    stmt = row['topic_statement'][:70]
    print(f'{i:3d}. [{valid}][{tier}] {lane:25s} {score:5.1f}  {stmt}')
print()
print(f'Total: {len(rows)} topics, {sum(1 for r in rows if r[\"valid_for_pool\"])} valid')
"
    exit 0
fi

# ── L2: WRITER (parallel) ─────────────────────────────────
echo ""
echo "▶ L2: Writer (parallel)"

WRITER_PACKETS=$(find "${ENGINE_OUT}/06_writer_packets" -name "writer_packet.json" -not -name "writer_packet_manifest.json" | sort)
PACKET_COUNT=$(echo "$WRITER_PACKETS" | grep -c "." || true)
echo "  Writing $PACKET_COUNT articles in parallel..."

# Check backend availability
BACKEND="auto"
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    BACKEND="anthropic"
elif [ -n "${OPENAI_API_KEY:-}" ]; then
    BACKEND="openai_compatible"
fi

WRITER_COMMON_ARGS="\
    --framework-specs-dir configs/frameworks \
    --lane-contract docs/lane_contracts/T01_single_lane_contract_v1.md \
    --article-draft-schema configs/writer/ARTICLE_DRAFT_SCHEMA.json \
    --humanizer-packet configs/writer/HUMANIZER_ZH_PACKET.json \
    --t01-signal-boost configs/writer/T01_SIGNAL_BOOST_FROM_DOTEY.json \
    --backend $BACKEND \
    --writer-model claude-sonnet-4-6 \
    --light-model claude-haiku-4-5-20251001 \
    --output-language zh-CN \
    --include-human-review-required \
    --no-self-improving-observe \
    --limit 1"

# Launch one writer process per packet, all in parallel
PIDS=()
for packet_path in $WRITER_PACKETS; do
    topic_id=$(basename "$(dirname "$packet_path")")
    topic_out="${WRITER_OUT}/${topic_id}"
    log_file="${WRITER_OUT}/${topic_id}.log"

    python3 pipeline/writer/writer.py \
        --writer-packet-root "$packet_path" \
        --out-root "$topic_out" \
        $WRITER_COMMON_ARGS \
        > "$log_file" 2>&1 &

    PIDS+=($!)
    echo "  ⚡ ${topic_id} (pid $!)"
done

# Wait for all writers to finish
FAILED=0
for pid in "${PIDS[@]}"; do
    if ! wait "$pid"; then
        FAILED=$((FAILED + 1))
    fi
done

echo "  ✓ Writer complete: $((PACKET_COUNT - FAILED))/$PACKET_COUNT succeeded"
if [ "$FAILED" -gt 0 ]; then
    echo "  ⚠ $FAILED articles failed — check logs in $WRITER_OUT/*.log"
fi

# ── L3: IMAGE ─────────────────────────────────────────────
if [ "$SKIP_IMAGES" = false ]; then
    echo ""
    echo "▶ L3: Image Generation"

    KIE_KEY="${KIE_API_KEY:-}"
    if [ -z "$KIE_KEY" ]; then
        echo "  ⚠ KIE_API_KEY not set, skipping image generation"
    else
        IMG_PIDS=()
        for article_json in $(find "$WRITER_OUT" -name "article_draft.json" | sort); do
            topic_dir=$(dirname "$article_json")
            topic_id=$(basename "$topic_dir")

            python3 pipeline/image/run_image_pipeline.py \
                --article "$article_json" \
                --brief-out "${topic_dir}/article_image_brief.json" \
                --images-out "${topic_dir}/image_assets" \
                --engine baoyu \
                --baoyu-provider kie \
                --generate \
                --max-inline "$MAX_INLINE" \
                > "${topic_dir}/image_gen.log" 2>&1 &

            IMG_PIDS+=($!)
            echo "  ⚡ ${topic_id} (pid $!)"
        done

        IMG_FAILED=0
        for pid in "${IMG_PIDS[@]}"; do
            if ! wait "$pid"; then
                IMG_FAILED=$((IMG_FAILED + 1))
            fi
        done
        echo "  ✓ Image generation complete: $((${#IMG_PIDS[@]} - IMG_FAILED))/${#IMG_PIDS[@]} succeeded"
    fi
else
    echo ""
    echo "▶ L3: Skipped (--skip-images)"
fi

# ── L4: PUBLISH ───────────────────────────────────────────
if [ "$SKIP_PUBLISH" = false ]; then
    echo ""
    echo "▶ L4: Publish"

    DATE=$(date +%Y-%m-%d)
    SLOT_NUM=1

    for article_json in $(find "$WRITER_OUT" -name "article_draft.json" | sort); do
        topic_dir=$(dirname "$article_json")
        topic_id=$(basename "$topic_dir")
        SLOT_DIR="runtime/accounts/${ACCOUNT}/publish_queue/${DATE}/$(printf '%02d' $SLOT_NUM)"
        mkdir -p "$SLOT_DIR"

        # Build publish slot: article + images + publish_spec with section-aware image placement
        python3 -c "
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, '.')
from pipeline.writer.formatter import build_article_blocks, build_publishing_hints, sanitize_article_blocks

article = json.load(open('$article_json'))
slot = Path('$SLOT_DIR')
topic_dir = Path('$topic_dir')

# Title + article md
(slot / 'title.txt').write_text(article['title'])
body = article.get('body_markdown', '')
md = f\"# {article['title']}\n\n> {article.get('dek','')}\n\n{body}\"
(slot / 'article.md').write_text(md)

# Copy images
assets = topic_dir / 'image_assets'
inline_paths = []
if assets.exists():
    cover = assets / 'cover_01/result_1.png'
    if cover.exists():
        shutil.copy2(cover, slot / 'cover.png')
    for i, img in enumerate(sorted(assets.glob('inline_*/result_1.png')), 1):
        dest = slot / f'inline_{i:02d}.png'
        shutil.copy2(img, dest)
        inline_paths.append(str(dest.resolve()))

# Build article_blocks
source_item = {'canonical_url': '', 'author': {}, 'source_assets': [], 'platform': 'x', 'source_kind': 'article'}
hints = build_publishing_hints(source_item, article.get('publishing_hints'))
blocks = build_article_blocks(title=article['title'], dek=article['dek'], body_markdown=body, publishing_hints=hints)
sanitized = sanitize_article_blocks(blocks, keep_hero_first=False)

# Find section end positions: insert image after each section's last content block
section_ends = []
current_end = 0
for i, b in enumerate(sanitized, 1):
    if b.get('type') == 'section_heading' and current_end > 0:
        section_ends.append(current_end)
    if b.get('type') in ('paragraph', 'bullet_list', 'quote'):
        current_end = i
# Last section ends at the last content block (but skip the very last block to not put image at article end)
if current_end > 0 and len(section_ends) < len(inline_paths):
    section_ends.append(current_end)

# Build inline_image_insertions: one image per section end
insertions = []
for idx, img_path in enumerate(inline_paths):
    if idx < len(section_ends):
        after = section_ends[idx]
    else:
        break  # more images than sections — skip extras
    insertions.append({
        'image_id': f'inline_{idx+1:02d}',
        'image_path': img_path,
        'after_block_ordinal': after,
    })

# Build publish spec
spec = {
    'publish_contract_version': 'article_publish_contract_v2',
    'title': article['title'],
    'dek': article['dek'],
    'article_blocks': sanitized,
    'inline_image_insertions': insertions,
}
(slot / 'article_publish_spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2))

print(f'  Slot {$SLOT_NUM}: {len(sanitized)} blocks, {len(insertions)} images at section ends')
"
        SLOT_NUM=$((SLOT_NUM + 1))
    done

    if [ "$DRY_RUN" = true ]; then
        echo "  dry-run mode: skipping actual publish"
    fi
    echo "  ✓ Publish queue assembled"
else
    echo ""
    echo "▶ L4: Skipped (--skip-publish)"
fi

# ── Summary ───────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════"
echo "  Pipeline Complete"
echo "  Run: ${RUN_ID}"
echo "  Output: ${RUN_ROOT}"
echo "════════════════════════════════════════════"
