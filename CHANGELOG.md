# Changelog

## [0.2.0] - 2026-04-06

### Changed
- Replaced direct Instagram Graph API with Composio SDK for publishing
- Replaced boto3/IAM keys with Bedrock bearer token (ABSK) via requests
- Replaced Cloudinary with imgbb for image hosting (free, simpler)
- Restructured src/ into generator/, publisher/, utils/ packages
- Updated prompt templates to generate X/Twitter posts and image overlay text
- Simplified from 8 dependencies to 5 (removed boto3, cloudinary, edge-tts, python-dotenv)
- Updated GitHub Actions workflow with new secrets and removed ffmpeg dependency

### Added
- config.json for content strategy (pillars, schedule, persona, image styles)
- Pillow template image generation (1080x1080 gradient + text overlay per pillar)
- X/Twitter publishing via Composio (graceful skip if not connected)
- Day-of-week content pillar scheduling
- imgbb image upload with 24h auto-expiry

### Removed
- Old scaffold files (content_generator, image_generator, tts_generator, video_maker, media_uploader, instagram_publisher)
- refresh-token.yml workflow (Composio handles auth)
- Cloudinary, edge-tts, ffmpeg, boto3 dependencies

## [0.1.0] - 2026-03-16

- Initial project scaffold with full automation pipeline
- CLAUDE.md with project context
