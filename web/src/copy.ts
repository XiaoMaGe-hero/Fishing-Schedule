// Every word the site shows lives here, in English.
export const copy = {
  siteName: "Liang's Fishing Schedule",
  tagline: "When to fish around Christchurch this week",

  video: { play: "Play video", none: "Video coming soon" },

  today: {
    heading: "Today",
    notRecommended: "Not recommended today",
    notRecommendedHint: "No good window in the rest of today. See the week below.",
    bestWindow: "Best window",
    passed: "Today's windows have passed",
    passedHint: "See the week below for the next one.",
    scoreOutOf: "out of 100",
  },

  week: {
    heading: "This week",
    empty: "No recommended windows in the next 7 days.",
    lowConfidence: "Low confidence",
    lowConfidenceHint: "More than 3 days out. Forecasts this far ahead often change.",
    whyHeading: "Why this score",
    skipped: "not scored",
    today: "Today",
    tomorrow: "Tomorrow",
    mapHeading: "Where the spots are",
  },

  timeline: {
    heading: "Conditions",
    chooseSpot: "Spot",
    tide: "Tide (m)",
    tideEstimated: "The tide curve is an estimate drawn between the official high and low tides.",
    wind: "Wind",
    gust: "Gusts",
    rain: "Chance of rain",
    wave: "Waves",
    swell: "Swell",
    showWind: "Wind and rain",
    showWaves: "Waves",
    swipeHint: "Swipe the chart to move through the week.",
    recommended: "Recommended",
    night: "Night",
  },

  tideTable: {
    heading: "Tide table",
    high: "High",
    low: "Low",
    sunrise: "Sunrise",
    sunset: "Sunset",
    moon: "Moon",
    offsetAssumed: "Times are for Lyttelton. This spot's own tide delay is not set yet.",
  },
  moonPhases: ["New moon", "Waxing crescent", "First quarter", "Waxing gibbous",
               "Full moon", "Waning gibbous", "Last quarter", "Waning crescent"],

  seaTemp: { heading: "Sea temperature", note: "Open-sea value for Pegasus Bay, not measured at the shore." },
  weather: { heading: "Weather", temp: "Air", rain: "Rain" },
  windTable: {
    heading: "Wind",
    speed: "km/h",
    gust: "Gust",
    onshore: "Onshore",
    offshore: "Offshore",
    cross: "Cross",
    unknown: "",
    from: "from",
  },

  river: {
    heading: "Waimakariri River flow",
    show: "Show the last 7 days",
    loading: "Loading river flow…",
    latest: "Latest",
    unit: "m³/s",
    site: "Measured at Old Highway Bridge",
    failed: "River flow could not be loaded. Tap to try again.",
  },

  freshness: {
    updated: (age: string) => `Updated ${age} ago`,
    stale: (age: string) => `Updated ${age} ago. This may be out of date.`,
    failed: (age: string) => `The last update failed. Showing data from ${age} ago.`,
    never: "No data yet",
    minutes: (n: number) => `${n} min`,
    hours: (n: number) => (n === 1 ? "1 hour" : `${n} hours`),
    days: (n: number) => (n === 1 ? "1 day" : `${n} days`),
  },

  errors: {
    loadTitle: "The forecast could not be loaded",
    loadBody: "Check your connection, then try again.",
    notConfigured: "This site has no data address yet. Set VITE_DATA_BASE_URL and rebuild.",
    retry: "Try again",
    partial: "Recommendations could not be loaded. Conditions are shown below.",
  },
  loading: "Loading the forecast…",

  footer: {
    sourcesHeading: "Data sources",
    sources: [
      { name: "Toitū Te Whenua Land Information New Zealand (LINZ)", what: "Tide predictions for Lyttelton", url: "https://www.linz.govt.nz/products-services/tides-and-tidal-streams/tide-predictions" },
      { name: "Open-Meteo", what: "Weather and marine forecasts", url: "https://open-meteo.com/" },
      { name: "Environment Canterbury", what: "Waimakariri River flow", url: "https://www.ecan.govt.nz/data/riverflow/" },
    ],
    updatesHeading: "Last updated",
    blocks: { tide: "Tides", forecast: "Weather and sea", flow: "River flow" },
    disclaimer: "Forecasts are a guide only. Look at the sea yourself before you fish.",
    mapCredit: "Map © OpenStreetMap contributors",
  },
};
