{
  "product": {
    "name": "ThreadOS",
    "type": "saas_app",
    "audience": "Independent fashion brand founders/operators (UK, Shopify-based, 1–20 employees)",
    "brand_attributes": [
      "trustworthy",
      "data-driven",
      "founder-friendly",
      "premium SaaS",
      "calm + decisive (no neon, no crypto, no futuristic AI)"
    ],
    "visual_style_mix": {
      "shopify_admin": "60% (navigation clarity, tables, density control)",
      "stripe": "25% (clean KPI cards, restrained color, strong hierarchy)",
      "notion": "15% (soft neutrals, subtle dividers, calm whitespace)"
    }
  },

  "design_personality": {
    "keywords": [
      "Calm operations cockpit",
      "Retail-native metrics",
      "Quiet luxury utility",
      "Fast scanning",
      "Explainable recommendations"
    ],
    "do": [
      "Use neutral surfaces with one strong primary ink color",
      "Use semantic risk colors sparingly and consistently",
      "Prefer borders + subtle shadows over gradients",
      "Make tables the hero; cards support scanning"
    ],
    "dont": [
      "No neon, no heavy gradients, no glassy sci-fi",
      "No overly saturated reds; use muted professional tones",
      "No decorative charts; every chart must answer a question",
      "No center-aligned app container"
    ]
  },

  "typography": {
    "google_fonts": {
      "heading": {
        "family": "Space Grotesk",
        "weights": [500, 600, 700],
        "usage": "Page titles, KPI numbers, section headers"
      },
      "body": {
        "family": "Inter",
        "weights": [400, 500, 600],
        "usage": "UI labels, tables, helper text"
      },
      "mono_optional": {
        "family": "IBM Plex Mono",
        "weights": [400, 500],
        "usage": "SKU codes, IDs, small technical labels"
      }
    },
    "tailwind_mapping": {
      "base": "font-sans",
      "headings": "font-[Space Grotesk] tracking-[-0.02em]",
      "numbers": "tabular-nums"
    },
    "type_scale": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl font-semibold",
      "h2": "text-base md:text-lg font-medium text-muted-foreground",
      "section_title": "text-sm font-semibold tracking-[0.02em] uppercase",
      "kpi_value": "text-2xl sm:text-3xl font-semibold",
      "table": "text-sm",
      "caption": "text-xs text-muted-foreground"
    },
    "copy_tone": {
      "locale": "UK English",
      "currency": "GBP (£)",
      "style": "Short, operational, no jargon. Prefer 'Reorder by' over 'Procurement date'."
    }
  },

  "layout_system": {
    "app_shell": {
      "sidebar": {
        "width": "w-[264px] (desktop)",
        "collapsed": "w-[72px] optional later; MVP can be fixed",
        "mobile": "Sheet drawer",
        "surface": "bg-card",
        "border": "border-r border-border"
      },
      "topbar": {
        "height": "h-14",
        "pattern": "Left: page title + breadcrumb; Right: search (optional), theme toggle, user menu",
        "border": "border-b border-border",
        "sticky": "sticky top-0 z-30 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60"
      },
      "content": {
        "max_width": "max-w-[1280px]",
        "padding": "px-4 sm:px-6 lg:px-8 py-6",
        "grid": "12-col on lg, 6-col on md, 1-col on mobile",
        "gaps": "gap-4 sm:gap-6"
      }
    },
    "page_header_pattern": {
      "title_row": "flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between",
      "title": "text-xl sm:text-2xl font-semibold",
      "subtitle": "text-sm text-muted-foreground",
      "actions": "Right-aligned buttons; primary action max 1 per page"
    }
  },

  "color_system": {
    "notes": [
      "Use shadcn CSS variables (HSL) for both themes.",
      "Primary is 'ink navy' (serious, Stripe-like). Accent is 'sage' for positive/healthy.",
      "Risk colors are semantic and muted; avoid pure saturated red.",
      "Gradients are decorative only and must stay under 20% viewport (see appended rules)."
    ],

    "light_theme_tokens_hsl": {
      "--background": "210 20% 98%",
      "--foreground": "222 47% 11%",

      "--card": "0 0% 100%",
      "--card-foreground": "222 47% 11%",

      "--popover": "0 0% 100%",
      "--popover-foreground": "222 47% 11%",

      "--primary": "222 47% 11%",
      "--primary-foreground": "210 40% 98%",

      "--secondary": "210 24% 96%",
      "--secondary-foreground": "222 47% 11%",

      "--muted": "210 24% 96%",
      "--muted-foreground": "215 16% 40%",

      "--accent": "210 24% 96%",
      "--accent-foreground": "222 47% 11%",

      "--destructive": "0 62% 52%",
      "--destructive-foreground": "210 40% 98%",

      "--border": "214 20% 90%",
      "--input": "214 20% 90%",
      "--ring": "222 47% 20%",

      "--radius": "0.75rem",

      "--chart-1": "222 47% 35%",
      "--chart-2": "160 35% 35%",
      "--chart-3": "38 70% 45%",
      "--chart-4": "200 45% 40%",
      "--chart-5": "0 55% 45%",

      "custom_semantic": {
        "--success": "160 45% 32%",
        "--success-bg": "160 45% 96%",
        "--warning": "38 85% 40%",
        "--warning-bg": "38 85% 95%",
        "--info": "200 70% 40%",
        "--info-bg": "200 70% 95%",
        "--risk-high": "0 55% 45%",
        "--risk-med": "38 85% 40%",
        "--risk-healthy": "160 45% 32%",
        "--focus": "222 47% 35%"
      }
    },

    "dark_theme_tokens_hsl": {
      "--background": "222 47% 7%",
      "--foreground": "210 40% 98%",

      "--card": "222 47% 9%",
      "--card-foreground": "210 40% 98%",

      "--popover": "222 47% 9%",
      "--popover-foreground": "210 40% 98%",

      "--primary": "210 40% 98%",
      "--primary-foreground": "222 47% 11%",

      "--secondary": "222 30% 14%",
      "--secondary-foreground": "210 40% 98%",

      "--muted": "222 30% 14%",
      "--muted-foreground": "215 20% 70%",

      "--accent": "222 30% 14%",
      "--accent-foreground": "210 40% 98%",

      "--destructive": "0 45% 35%",
      "--destructive-foreground": "210 40% 98%",

      "--border": "222 25% 18%",
      "--input": "222 25% 18%",
      "--ring": "210 40% 85%",

      "--chart-1": "210 40% 70%",
      "--chart-2": "160 35% 55%",
      "--chart-3": "38 70% 60%",
      "--chart-4": "200 45% 60%",
      "--chart-5": "0 55% 60%",

      "custom_semantic": {
        "--success": "160 35% 55%",
        "--success-bg": "160 35% 14%",
        "--warning": "38 70% 60%",
        "--warning-bg": "38 70% 14%",
        "--info": "200 45% 60%",
        "--info-bg": "200 45% 14%",
        "--risk-high": "0 55% 60%",
        "--risk-med": "38 70% 60%",
        "--risk-healthy": "160 35% 55%",
        "--focus": "210 40% 70%"
      }
    },

    "usage_rules": {
      "primary": "Use for primary buttons, active nav item, key emphasis.",
      "muted": "Use for secondary surfaces and subtle separators.",
      "semantic": "Use risk colors only for badges, small indicators, and alert callouts (not large backgrounds).",
      "charts": "Use chart tokens consistently across pages; avoid rainbow palettes."
    }
  },

  "spacing_and_density": {
    "principles": [
      "Operator-first: readable tables, not cramped.",
      "Use 2–3x more spacing than feels comfortable.",
      "Prefer 8px grid increments."
    ],
    "tokens": {
      "--space-1": "0.25rem",
      "--space-2": "0.5rem",
      "--space-3": "0.75rem",
      "--space-4": "1rem",
      "--space-5": "1.25rem",
      "--space-6": "1.5rem",
      "--space-8": "2rem",
      "--space-10": "2.5rem"
    },
    "table_density": {
      "row_height": "h-12 (default), h-10 (dense toggle later)",
      "cell_padding": "px-3 py-2",
      "header": "text-xs uppercase tracking-wide text-muted-foreground"
    }
  },

  "components": {
    "component_path": {
      "shadcn": {
        "button": "/app/frontend/src/components/ui/button.jsx",
        "badge": "/app/frontend/src/components/ui/badge.jsx",
        "card": "/app/frontend/src/components/ui/card.jsx",
        "table": "/app/frontend/src/components/ui/table.jsx",
        "tabs": "/app/frontend/src/components/ui/tabs.jsx",
        "input": "/app/frontend/src/components/ui/input.jsx",
        "select": "/app/frontend/src/components/ui/select.jsx",
        "dropdown_menu": "/app/frontend/src/components/ui/dropdown-menu.jsx",
        "sheet": "/app/frontend/src/components/ui/sheet.jsx",
        "drawer": "/app/frontend/src/components/ui/drawer.jsx",
        "dialog": "/app/frontend/src/components/ui/dialog.jsx",
        "tooltip": "/app/frontend/src/components/ui/tooltip.jsx",
        "skeleton": "/app/frontend/src/components/ui/skeleton.jsx",
        "sonner_toast": "/app/frontend/src/components/ui/sonner.jsx",
        "switch": "/app/frontend/src/components/ui/switch.jsx",
        "separator": "/app/frontend/src/components/ui/separator.jsx",
        "scroll_area": "/app/frontend/src/components/ui/scroll-area.jsx",
        "calendar": "/app/frontend/src/components/ui/calendar.jsx"
      },
      "recommended_additions": {
        "framer_motion": "Micro-interactions + page transitions",
        "recharts": "Charts",
        "lucide_react": "Icons"
      }
    },

    "button_hierarchy": {
      "primary": {
        "usage": "Main action per page (e.g., 'Generate recommendations', 'Export CSV')",
        "classes": "rounded-[var(--radius)] shadow-sm hover:shadow-md transition-shadow transition-colors",
        "states": {
          "hover": "bg-primary/90",
          "active": "scale-[0.99]",
          "focus": "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        },
        "data_testid_examples": [
          "dashboard-primary-action-button",
          "recommendations-export-button"
        ]
      },
      "secondary": {
        "usage": "Secondary actions (filters, compare)",
        "classes": "bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors",
        "data_testid_examples": [
          "inventory-filter-button"
        ]
      },
      "ghost": {
        "usage": "Icon buttons in topbar, table row actions",
        "classes": "hover:bg-accent transition-colors",
        "data_testid_examples": [
          "topbar-theme-toggle-button",
          "table-row-actions-button"
        ]
      }
    },

    "kpi_tile": {
      "pattern": "Card with label, value, delta chip, and tiny sparkline (optional).",
      "layout": "flex items-start justify-between gap-3",
      "value": "font-[Space Grotesk] tabular-nums",
      "delta_chip": "Badge variant='secondary' with up/down icon",
      "skeleton": "Use <Skeleton className='h-6 w-24' /> for value",
      "data_testid_examples": [
        "kpi-inventory-value",
        "kpi-total-units",
        "kpi-days-of-stock",
        "kpi-low-stock-alert-count"
      ]
    },

    "tables": {
      "inventory_table": {
        "features": [
          "Sticky header",
          "Row hover highlight",
          "Sortable columns",
          "Filter row (category, risk, search)",
          "Row click navigates to SKU detail"
        ],
        "row_hover": "hover:bg-muted/60",
        "selected_row": "bg-muted",
        "numeric_alignment": "text-right tabular-nums",
        "data_testid_examples": [
          "inventory-table",
          "inventory-search-input",
          "inventory-category-select",
          "inventory-risk-select",
          "inventory-table-row"
        ]
      },
      "best_sellers_slow_movers": {
        "pattern": "Two cards side-by-side on desktop; stacked on mobile.",
        "columns": ["SKU", "Product", "Units (30d)", "Sell-through"],
        "data_testid_examples": [
          "dashboard-best-sellers-table",
          "dashboard-slow-movers-table"
        ]
      }
    },

    "badges_and_risk": {
      "risk_badge_variants": {
        "high_stockout": {
          "label": "High stockout risk",
          "bg": "bg-[hsl(var(--risk-high))]/10",
          "text": "text-[hsl(var(--risk-high))]",
          "border": "border-[hsl(var(--risk-high))]/20"
        },
        "medium_stockout": {
          "label": "Medium stockout risk",
          "bg": "bg-[hsl(var(--risk-med))]/10",
          "text": "text-[hsl(var(--risk-med))]",
          "border": "border-[hsl(var(--risk-med))]/20"
        },
        "high_overstock": {
          "label": "High overstock risk",
          "bg": "bg-[hsl(var(--warning))]/10",
          "text": "text-[hsl(var(--warning))]",
          "border": "border-[hsl(var(--warning))]/20"
        },
        "medium_overstock": {
          "label": "Medium overstock risk",
          "bg": "bg-[hsl(var(--warning))]/10",
          "text": "text-[hsl(var(--warning))]",
          "border": "border-[hsl(var(--warning))]/20"
        },
        "healthy": {
          "label": "Healthy",
          "bg": "bg-[hsl(var(--success))]/10",
          "text": "text-[hsl(var(--success))]",
          "border": "border-[hsl(var(--success))]/20"
        }
      },
      "confidence_indicator": {
        "pattern": "Progress bar + label (e.g., 'Confidence: 82%')",
        "component": "progress",
        "classes": "h-2 rounded-full",
        "data_testid_examples": [
          "forecast-confidence-progress",
          "recommendation-confidence-progress"
        ]
      }
    },

    "charts_recharts": {
      "global_chart_style": {
        "grid": "stroke: hsl(var(--border))",
        "axis": "tick fill: hsl(var(--muted-foreground)) font-size: 12",
        "tooltip": "Use shadcn Card-like tooltip with bg-card border-border",
        "line": "stroke: hsl(var(--chart-1)) strokeWidth: 2",
        "area_fill": "fill: hsl(var(--chart-1)) opacity: 0.12",
        "reference_line": "strokeDasharray: '4 4' stroke: hsl(var(--muted-foreground))"
      },
      "recent_sales_chart": {
        "type": "AreaChart",
        "x": "date (last 30 days)",
        "y": "daily units",
        "data_testid_examples": [
          "dashboard-recent-sales-chart"
        ]
      },
      "sku_sales_history": {
        "type": "ComposedChart (bar for units + line for trend)",
        "data_testid_examples": [
          "sku-sales-history-chart"
        ]
      }
    },

    "navigation": {
      "sidebar_item": {
        "pattern": "Icon + label, active state uses subtle left border + muted background",
        "classes": {
          "base": "flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors",
          "active": "bg-muted text-foreground border border-border"
        },
        "data_testid_examples": [
          "sidebar-nav-dashboard",
          "sidebar-nav-inventory",
          "sidebar-nav-forecasting",
          "sidebar-nav-recommendations",
          "sidebar-nav-risks"
        ]
      },
      "topbar_controls": {
        "theme_toggle": "Use shadcn Switch or Button(ghost) with sun/moon icons; persist to localStorage",
        "user_menu": "DropdownMenu with account + logout",
        "data_testid_examples": [
          "topbar-theme-toggle",
          "topbar-user-menu"
        ]
      },
      "lucide_icons": {
        "dashboard": "LayoutDashboard",
        "inventory": "Boxes",
        "product_detail": "Shirt",
        "forecasting": "LineChart",
        "recommendations": "ShoppingBag",
        "risks": "ShieldAlert",
        "login": "LogIn",
        "settings_optional": "Settings"
      }
    }
  },

  "motion_and_microinteractions": {
    "library": "framer-motion",
    "principles": [
      "Motion should clarify state changes (filter applied, drawer opened, row selected).",
      "Keep durations short; avoid bouncy easing in B2B contexts."
    ],
    "tokens": {
      "duration_fast": 0.12,
      "duration_base": 0.18,
      "ease": "[0.2, 0.8, 0.2, 1]"
    },
    "patterns": {
      "page_enter": "Fade + slight y translate (6px)",
      "drawer": "Slide from right with opacity",
      "kpi_hover": "Shadow lift only (no transform on container to avoid layout jitter)",
      "table_row_hover": "Background tint only"
    }
  },

  "states": {
    "loading": {
      "pattern": "Skeletons for KPI tiles + table rows; keep layout stable.",
      "components": ["skeleton"],
      "data_testid_examples": [
        "dashboard-loading-skeleton",
        "inventory-loading-skeleton"
      ]
    },
    "empty": {
      "pattern": "Card with icon, short explanation, and one action (reset filters / import / view all).",
      "copy_examples": {
        "inventory_zero_results": "No SKUs match your filters. Try clearing risk or category filters.",
        "recommendations_none": "No buy recommendations right now. Your inventory looks stable for the next 30 days."
      },
      "data_testid_examples": [
        "inventory-empty-state",
        "recommendations-empty-state"
      ]
    },
    "error": {
      "pattern": "Inline Alert component at top of content area; include retry button.",
      "components": ["alert", "button"],
      "data_testid_examples": [
        "global-error-alert",
        "retry-fetch-button"
      ]
    }
  },

  "page_by_page_wireframes": {
    "/login": {
      "layout": "Split layout on desktop: left brand panel (subtle texture), right login card. On mobile: stacked.",
      "left_panel": {
        "content": [
          "ThreadOS wordmark",
          "1-line value prop: 'Inventory decisions you can defend.'",
          "3 bullets: Reduce stockouts, avoid overbuying, protect cash"
        ],
        "background": "Use subtle noise + fabric image at 10–15% opacity"
      },
      "right_panel": {
        "card": "Email + password + Sign in button",
        "demo_hint": "Small muted callout with demo credentials",
        "data_testid": {
          "email": "login-email-input",
          "password": "login-password-input",
          "submit": "login-submit-button",
          "demo_hint": "login-demo-credentials-hint"
        }
      }
    },

    "/dashboard": {
      "sections": [
        "Page header (title + date range selector optional)",
        "KPI row (4 cards)",
        "Recent sales chart (full width)",
        "Two-column: Best sellers + Slow movers",
        "Low stock alerts list/table"
      ],
      "grid": {
        "kpis": "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4",
        "lower": "grid grid-cols-1 lg:grid-cols-2 gap-6"
      },
      "data_testid": {
        "kpi_row": "dashboard-kpi-row",
        "recent_sales": "dashboard-recent-sales-section",
        "best_sellers": "dashboard-best-sellers-section",
        "slow_movers": "dashboard-slow-movers-section",
        "low_stock": "dashboard-low-stock-alerts-section"
      }
    },

    "/inventory": {
      "sections": [
        "Page header with search + filters",
        "Filter bar: Category Select, Risk Select, Sort Select",
        "Inventory table",
        "Pagination (if needed later)"
      ],
      "interaction": "Row click -> /products/:id. Right side optional Drawer for quick peek (later).",
      "data_testid": {
        "search": "inventory-search-input",
        "table": "inventory-table"
      }
    },

    "/products/:id": {
      "sections": [
        "Header: Product name + SKU + category + risk badge",
        "Top metrics: Current stock, 30d units sold, Days of stock",
        "Sales history chart (90 days)",
        "Forecast cards (30/60/90) with confidence",
        "Buy recommendation block (qty + reorder date + explanation)",
        "Risk explanation panel (why flagged)"
      ],
      "layout": "Use 2-column on lg: left charts, right recommendation + risk. Stack on mobile.",
      "data_testid": {
        "stock": "sku-current-stock",
        "forecast_30": "sku-forecast-30-card",
        "forecast_60": "sku-forecast-60-card",
        "forecast_90": "sku-forecast-90-card",
        "recommendation": "sku-buy-recommendation",
        "risk": "sku-risk-explanation"
      }
    },

    "/forecasting": {
      "sections": [
        "Header: Forecasting overview",
        "Controls: search + category + confidence sort",
        "Table: SKU, current stock, 30/60/90 forecast, confidence",
        "Inline mini trend sparkline per row (optional)"
      ],
      "data_testid": {
        "table": "forecasting-table",
        "confidence_sort": "forecasting-confidence-sort"
      }
    },

    "/recommendations": {
      "sections": [
        "Header: Buy recommendations",
        "Table: SKU, current stock, forecast demand, recommended qty, reorder date, confidence",
        "Explanation drawer (right) opens on row click"
      ],
      "drawer": {
        "content": [
          "Summary: 'Order 120 units by 14 Jun'",
          "Why this quantity (bullets)",
          "Why this date (lead time + trend)",
          "Risk if not ordered"
        ],
        "components": ["drawer"],
        "data_testid": {
          "table": "recommendations-table",
          "drawer": "recommendations-explanation-drawer"
        }
      }
    },

    "/risks": {
      "sections": [
        "Header: Risk centre",
        "5 bucket cards (counts + short definition)",
        "Below: Tabs or filterable list by bucket",
        "Each SKU row shows badge + 1-line explanation"
      ],
      "bucket_cards": {
        "layout": "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4",
        "visual": "Small left color bar + count + label",
        "data_testid": {
          "bucket_high_stockout": "risk-bucket-high-stockout",
          "bucket_medium_stockout": "risk-bucket-medium-stockout",
          "bucket_high_overstock": "risk-bucket-high-overstock",
          "bucket_medium_overstock": "risk-bucket-medium-overstock",
          "bucket_healthy": "risk-bucket-healthy"
        }
      }
    }
  },

  "image_urls": [
    {
      "category": "login_left_panel_texture",
      "description": "Subtle fabric texture overlay (use at 10–15% opacity, add noise layer).",
      "url": "https://images.unsplash.com/photo-1619263719761-165c773ee5df?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2Mzl8MHwxfHNlYXJjaHwzfHx0ZXh0aWxlJTIwZmFicmljJTIwY2xvc2UlMjB1cCUyMG5ldXRyYWx8ZW58MHx8fHdoaXRlfDE3ODEyNjEwNTJ8MA&ixlib=rb-4.1.0&q=85"
    },
    {
      "category": "login_left_panel_palette_reference",
      "description": "Muted colour dots image; can be used as a tiny blurred background accent behind the wordmark (very subtle).",
      "url": "https://images.unsplash.com/photo-1523456836369-09236da4c580?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2Mzl8MHwxfHNlYXJjaHwxfHx0ZXh0aWxlJTIwZmFicmljJTIwY2xvc2UlMjB1cCUyMG5ldXRyYWx8ZW58MHx8fHdoaXRlfDE3ODEyNjEwNTJ8MA&ixlib=rb-4.1.0&q=85"
    },
    {
      "category": "dark_mode_texture",
      "description": "Dark textile texture for dark mode decorative panel (use at 8–12% opacity).",
      "url": "https://images.unsplash.com/photo-1551381912-4e2e29c7fd17?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2Mzl8MHwxfHNlYXJjaHwyfHx0ZXh0aWxlJTIwZmFicmljJTIwY2xvc2UlMjB1cCUyMG5ldXRyYWx8ZW58MHx8fHdoaXRlfDE3ODEyNjEwNTJ8MA&ixlib=rb-4.1.0&q=85"
    }
  ],

  "instructions_to_main_agent": {
    "theme_toggle": [
      "Default to light theme on first login.",
      "Persist theme in localStorage key: 'threados-theme' with values 'light'|'dark'.",
      "Apply 'dark' class on <html> or <body>.",
      "Theme toggle control must include data-testid='topbar-theme-toggle'."
    ],
    "currency_format": [
      "Use Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).",
      "Use tabular-nums for all currency + unit columns."
    ],
    "tables": [
      "Use shadcn Table primitives; keep header sticky for long lists.",
      "Every sortable header is a Button(ghost) with data-testid='inventory-sort-<column>'.",
      "Row click target should be the entire row with data-testid='inventory-row-<sku>'."
    ],
    "charts": [
      "Use recharts with CSS variables for colors (hsl(var(--chart-1))).",
      "Tooltips should be custom and match Card styling."
    ],
    "accessibility": [
      "WCAG AA contrast in both themes.",
      "Visible focus rings on all interactive elements.",
      "Respect prefers-reduced-motion (reduce framer-motion durations to 0)."
    ],
    "js_files": [
      "All components are .jsx; keep guidelines and examples in JS/JSX (no TSX).",
      "Use named exports for components; pages default export."
    ]
  },

  "appendix_general_ui_ux_design_guidelines": "<General UI UX Design Guidelines>\n    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms\n    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text\n   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json\n\n **GRADIENT RESTRICTION RULE**\nNEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc\nNEVER use dark gradients for logo, testimonial, footer etc\nNEVER let gradients cover more than 20% of the viewport.\nNEVER apply gradients to text-heavy content or reading areas.\nNEVER use gradients on small UI elements (<100px width).\nNEVER stack multiple gradient layers in the same viewport.\n\n**ENFORCEMENT RULE:**\n    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors\n\n**How and where to use:**\n   • Section backgrounds (not content backgrounds)\n   • Hero section header content. Eg: dark to light to dark color\n   • Decorative overlays and accent elements only\n   • Hero section with 2-3 mild color\n   • Gradients creation can be done for any angle say horizontal, vertical or diagonal\n\n- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**\n\n</Font Guidelines>\n\n- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. \n   \n- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.\n\n- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.\n   \n- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly\n    Eg: - if it implies playful/energetic, choose a colorful scheme\n           - if it implies monochrome/minimal, choose a black–white/neutral scheme\n\n**Component Reuse:**\n\t- Prioritize using pre-existing components from src/components/ui when applicable\n\t- Create new components that match the style and conventions of existing components when needed\n\t- Examine existing components to understand the project's component patterns before creating new ones\n\n**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component\n\n**Best Practices:**\n\t- Use Shadcn/UI as the primary component library for consistency and accessibility\n\t- Import path: ./components/[component-name]\n\n**Export Conventions:**\n\t- Components MUST use named exports (export const ComponentName = ...)\n\t- Pages MUST use default exports (export default function PageName() {...})\n\n**Toasts:**\n  - Use `sonner` for toasts\"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`\n\nUse 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.\n</General UI UX Design Guidelines>"
}
