# Frontend Dashboard

React 18 + TypeScript + Tailwind CSS dashboard for the Brown GPU cluster ops agent.

## Goals

- Show 14 GPU node health cards.
- Display GPU memory, utilization, temperature, and power.
- Stream inspection output from Nanobot over WebSocket.
- Provide a diagnosis panel for natural-language questions.

## Planned Commands

```bash
npm install
npm run dev
```

## Data Source

The first implementation should read inspection JSON from `reports/`. Later it can connect to the Nanobot gateway through WebSocket.
