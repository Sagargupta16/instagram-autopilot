#!/usr/bin/env bash
# Install ffmpeg (with ffprobe) on the Ubuntu Actions runner.
#
# On 2026-10-24 `apt-get update` hung on the runner's mirror for 19 minutes and the job ran out
# of time before rendering anything. Each try is time-boxed and retried, so a slow mirror costs
# minutes instead of the whole run.
set -u

for attempt in 1 2 3; do
  if timeout 180 sudo apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 update -qq \
    && timeout 300 sudo apt-get install -y -qq ffmpeg; then
    ffmpeg -hide_banner -version | head -1
    exit 0
  fi
  echo "::warning::ffmpeg install try ${attempt} of 3 failed or timed out; retrying"
  sudo dpkg --configure -a || true # finish anything a killed try left half-installed
  sleep $((attempt * 10))
done
echo "::error::ffmpeg could not be installed after 3 tries" >&2
exit 1
