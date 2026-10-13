// Tailwind design tokens — copied from the Stitch "Academic Support Operations" design system.
tailwind.config = {
  theme: {
    extend: {
      colors: {
        "surface": "#f9f9ff", "surface-dim": "#d6dae7", "surface-bright": "#f9f9ff",
        "surface-container-lowest": "#ffffff", "surface-container-low": "#f1f3ff",
        "surface-container": "#eaedfb", "surface-container-high": "#e4e8f5",
        "surface-container-highest": "#dfe2f0", "surface-variant": "#dfe2f0",
        "on-surface": "#171c25", "on-surface-variant": "#544246",
        "inverse-surface": "#2c303b", "inverse-on-surface": "#edf0fe",
        "outline": "#877276", "outline-variant": "#dac0c5", "surface-tint": "#9c3e5c",
        "primary": "#4d0021", "on-primary": "#ffffff", "primary-container": "#6b1736",
        "on-primary-container": "#ee809f", "inverse-primary": "#ffb1c4",
        "primary-fixed": "#ffd9e0", "primary-fixed-dim": "#ffb1c4",
        "on-primary-fixed": "#3f001a", "on-primary-fixed-variant": "#7e2644",
        "secondary": "#605d65", "on-secondary": "#ffffff", "secondary-container": "#e6e0ea",
        "on-secondary-container": "#66636b", "secondary-fixed": "#e6e0ea", "secondary-fixed-dim": "#cac5ce",
        "on-secondary-fixed": "#1c1b21", "on-secondary-fixed-variant": "#48454d",
        "tertiary": "#002a0e", "on-tertiary": "#ffffff", "tertiary-container": "#00421b",
        "on-tertiary-container": "#74af7d", "tertiary-fixed": "#b3f2ba", "tertiary-fixed-dim": "#97d59f",
        "on-tertiary-fixed": "#00210a", "on-tertiary-fixed-variant": "#165128",
        "error": "#ba1a1a", "on-error": "#ffffff", "error-container": "#ffdad6", "on-error-container": "#93000a",
        "background": "#f9f9ff", "on-background": "#171c25",
        "line": "#E5E7EB", "canvas": "#F7F7F9", "charcoal": "#25232A", "slate": "#737783"
      },
      borderRadius: { DEFAULT: "0.25rem", lg: "0.5rem", xl: "0.75rem", "2xl": "1rem", full: "9999px" },
      spacing: {
        "space-xs": "0.25rem", "space-sm": "0.5rem", "space-md": "1rem", "space-lg": "1.5rem",
        "space-xl": "2rem", "gutter": "1.5rem", "gutter-mobile": "1rem", "margin": "2rem", "margin-mobile": "1rem"
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        "headline-xl": ["Inter"], "headline-lg": ["Inter"], "headline-md": ["Inter"], "title-sm": ["Inter"],
        "body-lg": ["Inter"], "body-md": ["Inter"], "body-sm": ["Inter"], "label-md": ["Inter"],
        "label-sm": ["Inter"], "caption": ["Inter"], "headline-xl-mobile": ["Inter"]
      },
      fontSize: {
        "headline-xl": ["32px", { lineHeight: "40px", letterSpacing: "-0.02em", fontWeight: "700" }],
        "headline-xl-mobile": ["26px", { lineHeight: "34px", letterSpacing: "-0.015em", fontWeight: "700" }],
        "headline-lg": ["24px", { lineHeight: "32px", letterSpacing: "-0.015em", fontWeight: "600" }],
        "headline-md": ["20px", { lineHeight: "28px", letterSpacing: "-0.01em", fontWeight: "600" }],
        "title-sm": ["16px", { lineHeight: "24px", letterSpacing: "-0.005em", fontWeight: "600" }],
        "body-lg": ["16px", { lineHeight: "24px", fontWeight: "400" }],
        "body-md": ["14px", { lineHeight: "20px", fontWeight: "400" }],
        "body-sm": ["13px", { lineHeight: "18px", fontWeight: "400" }],
        "label-md": ["13px", { lineHeight: "18px", letterSpacing: "0.01em", fontWeight: "600" }],
        "label-sm": ["12px", { lineHeight: "16px", letterSpacing: "0.02em", fontWeight: "500" }],
        "caption": ["11px", { lineHeight: "14px", letterSpacing: "0.03em", fontWeight: "500" }]
      },
      boxShadow: {
        card: "0 1px 2px 0 rgba(0,0,0,0.05)",
        float: "0 10px 15px -3px rgba(37,35,42,0.08), 0 4px 6px -2px rgba(37,35,42,0.04)"
      }
    }
  }
};
