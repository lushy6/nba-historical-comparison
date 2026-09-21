"use client";

import Image from "next/image";
import { useState } from "react";

import type { Profile } from "@/lib/types";

import styles from "./entity-avatar.module.css";

const SIZES: Record<"small" | "medium" | "large", number> = {
  small: 32,
  medium: 48,
  large: 64,
};

type EntityAvatarProps = {
  entity: Profile;
  size: "small" | "medium" | "large";
  decorative?: boolean;
};

type ImageState = {
  source: string;
  loading: boolean;
  failed: boolean;
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function isAllowedImageUrl(imageUrl: string | null): imageUrl is string {
  if (!imageUrl) return false;
  try {
    const url = new URL(imageUrl);
    return url.origin === "https://cdn.nba.com";
  } catch {
    return false;
  }
}

export function EntityAvatar({ entity, size, decorative = false }: EntityAvatarProps) {
  const px = SIZES[size];
  const imageUrl = isAllowedImageUrl(entity.visual.image_url) ? entity.visual.image_url : null;
  const source = `${entity.id}\u0000${imageUrl ?? ""}`;
  const [imageState, setImageState] = useState<ImageState>(() => ({
    source,
    loading: Boolean(imageUrl),
    failed: false,
  }));
  const sourceChanged = imageState.source !== source;
  const failed = !sourceChanged && imageState.failed;
  const loading = Boolean(imageUrl) && (sourceChanged || imageState.loading);
  const showImage = Boolean(imageUrl) && !failed;
  const mono = initials(entity.name);

  const frameStyle: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: px,
    height: px,
    flexShrink: 0,
    borderRadius: entity.visual.kind === "player" ? "50%" : "0.375rem",
    overflow: "hidden",
    background: "var(--line, #dedfd9)",
    position: "relative",
  };

  const fallbackProps = decorative
    ? { "aria-hidden": true }
    : !showImage
      ? { "aria-label": entity.name }
      : {};

  function markLoaded() {
    setImageState({ source, loading: false, failed: false });
  }

  function markFailed() {
    setImageState({ source, loading: false, failed: true });
  }

  return (
    <span style={frameStyle} {...fallbackProps}>
      {showImage ? (
        <span className={styles.media}>
          <Image
            key={source}
            src={imageUrl!}
            alt={decorative ? "" : entity.name}
            fill
            sizes={`${px}px`}
            className={styles.image}
            onLoad={markLoaded}
            onError={markFailed}
          />
          {loading && <span aria-hidden="true" className={styles.skeleton} data-testid="avatar-skeleton" />}
        </span>
      ) : (
        <span aria-hidden="true" style={{ fontSize: px * 0.35, fontWeight: 650, color: "var(--muted-ink, #6f716c)", lineHeight: 1 }}>
          {mono}
        </span>
      )}
    </span>
  );
}
