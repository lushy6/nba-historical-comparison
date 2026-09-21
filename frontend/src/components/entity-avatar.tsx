"use client";

import { useState } from "react";

import type { Profile } from "@/lib/types";


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

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function EntityAvatar({ entity, size, decorative = false }: EntityAvatarProps) {
  const [failed, setFailed] = useState(false);
  const px = SIZES[size];
  const mono = initials(entity.name);
  const imageUrl = entity.visual.image_url;
  const showImage = Boolean(imageUrl) && !failed;

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

  if (decorative) {
    return (
      <span style={frameStyle} aria-hidden="true">
        {!showImage && (
          <span style={{ fontSize: px * 0.35, fontWeight: 650, color: "var(--muted-ink, #6f716c)", lineHeight: 1 }}>
            {mono}
          </span>
        )}
        {showImage && (
          <img
            src={imageUrl!}
            alt=""
            width={px}
            height={px}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            onError={() => setFailed(true)}
          />
        )}
      </span>
    );
  }

  return (
    <span style={frameStyle} aria-label={entity.name}>
      {showImage ? (
        <img
          src={imageUrl!}
          alt={entity.name}
          width={px}
          height={px}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
          onError={() => setFailed(true)}
        />
      ) : (
        <span
          aria-hidden="true"
          style={{ fontSize: px * 0.35, fontWeight: 650, color: "var(--muted-ink, #6f716c)", lineHeight: 1 }}
        >
          {mono}
        </span>
      )}
    </span>
  );
}
