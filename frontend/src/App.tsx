import { Activity, Bot, Cpu, HardDrive, MessageSquare, Network, Send, Server, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import type { ChatMessage, ClusterNode, DashboardStatus, ExtensionNode, HealthStatus, InspectionFinding, LocalMetric } from "./types";

const fallbackMetrics: LocalMetric[] = [
  { label: "CPU", value: "18%", status: "normal", detail: "负载较低，适合继续运行巡检任务" },
  { label: "内存", value: "1.0 / 7.8 GiB", status: "normal", detail: "可用内存充足" },
  { label: "磁盘", value: "1%", status: "normal", detail: "项目卷和 Docker 空间正常" },
  { label: "Nanobot", value: "Running", status: "normal", detail: "ops-agent 容器和 health endpoint 正常" },
];

const fallbackFindings: InspectionFinding[] = [
  {
    title: "本机巡检通过",
    severity: "normal",
    evidence: "容器内 health endpoint 返回 {\"status\":\"ok\"}",
    recommendation: "下一步接入 reports/latest.json，让看板读取真实巡检数据。",
  },
  {
    title: "宿主机端口访问差异",
    severity: "warning",
    evidence: "Docker Desktop for Mac 下 host network 与 Linux 行为不同",
    recommendation: "本机验证优先使用 docker exec 访问容器内 127.0.0.1:18790。",
  },
];

const extensionNodes: ExtensionNode[] = [
  { id: "local-machine", role: "MVP 节点", status: "normal", note: "当前实际监控对象" },
  { id: "gpu-node-01..14", role: "Brown GPU 集群", status: "unknown", note: "保留扩展接口，暂未接入" },
  { id: "sidecar-agent", role: "远程采集器", status: "unknown", note: "后续通过 SSH 或 sidecar 采集指标" },
];

const initialMessages: ChatMessage[] = [
  {
    role: "agent",
    content: "我可以帮你解释节点状态、触发巡检、分析日志，并逐步扩展到 Brown 实验室的多台 GPU 节点。",
  },
  {
    role: "user",
    content: "现在机器状态怎么样？",
  },
  {
    role: "agent",
    content: "当前看板会读取真实巡检 API；如果配置了 nodes.json，会展示本机和远程服务器的多节点状态。",
  },
];

const statusLabel: Record<HealthStatus, string> = {
  normal: "正常",
  warning: "关注",
  critical: "异常",
  unknown: "待接入",
};

const statusClass: Record<HealthStatus, string> = {
  normal: "border-emerald-500 bg-emerald-50 text-emerald-950",
  warning: "border-amber-500 bg-amber-50 text-amber-950",
  critical: "border-rose-500 bg-rose-50 text-rose-950",
  unknown: "border-slate-300 bg-white text-slate-700",
};

export default function App() {
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [status, setStatus] = useState<DashboardStatus>({
    timestamp: null,
    overallStatus: "unknown",
    metrics: fallbackMetrics,
    findings: fallbackFindings,
  });
  const [statusLoading, setStatusLoading] = useState(false);
  const metrics = status.metrics?.length ? status.metrics : metricsFromNodes(status.nodes);
  const nodes = status.nodes?.length ? status.nodes : extensionNodes;

  async function loadStatus() {
    setStatusLoading(true);
    try {
      const response = await fetch("/api/status");
      if (!response.ok) {
        throw new Error(`status API returned ${response.status}`);
      }
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      setStatus((current) => ({
        ...current,
        overallStatus: "warning",
        findings: [
          {
            title: "无法读取真实状态",
            severity: "warning",
            evidence: error instanceof Error ? error.message : "unknown error",
            recommendation: "确认 ops-agent 容器已启动，并且 8787 API channel 可访问。",
          },
        ],
      }));
    } finally {
      setStatusLoading(false);
    }
  }

  useEffect(() => {
    loadStatus();
  }, []);

  async function sendMessage() {
    const trimmed = input.trim();
    if (!trimmed || isSending) return;

    setInput("");
    setIsSending(true);
    setMessages((current) => [
      ...current,
      { role: "user", content: trimmed },
      { role: "agent", content: "正在发送给 Nanobot Agent，等待诊断结果...", pending: true },
    ]);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: trimmed,
          conversationId: "dashboard-main",
        }),
      });

      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }

      const data = await response.json();
      const reply = data.messages?.map((message: { content: string }) => message.content).join("\n\n") || "Nanobot 没有返回内容。";

      setMessages((current) => [
        ...current.filter((message) => !message.pending),
        { role: "agent", content: reply },
      ]);
      await loadStatus();
    } catch (error) {
      setMessages((current) => [
        ...current.filter((message) => !message.pending),
        {
          role: "agent",
          content: `调用 Nanobot API 失败：${error instanceof Error ? error.message : "unknown error"}`,
          error: true,
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-100 text-slate-950">
      <section className="mx-auto max-w-7xl px-5 py-6">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">Local MVP / Multi-node Ready</p>
            <h1 className="mt-1 text-3xl font-semibold">智能运维 Agent 看板</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">
              当前已支持本机和 SSH 远程节点巡检，后续可按同一节点模型扩展到 Brown 14 台 GPU 服务器。
            </p>
          </div>
          <div className={`rounded-md border px-4 py-2 text-sm font-medium ${statusClass[status.overallStatus]}`}>
            整体状态：{statusLabel[status.overallStatus]}
          </div>
        </header>

        <div className="mt-6 grid gap-5 xl:grid-cols-[1.35fr_0.9fr]">
          <section className="space-y-5">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {metrics.map((metric) => (
                <article key={metric.label} className={`rounded-md border-l-4 bg-white p-4 shadow-sm ${statusClass[metric.status]}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      {metricIcon(metric.label)}
                      <h2 className="text-sm font-semibold">{metric.label}</h2>
                    </div>
                    <span className="text-xs">{statusLabel[metric.status]}</span>
                  </div>
                  <p className="mt-3 text-2xl font-semibold">{metric.value}</p>
                  <p className="mt-2 text-xs leading-5 text-slate-600">{metric.detail}</p>
                </article>
              ))}
            </div>

            <section className="rounded-md bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">最近巡检摘要</h2>
                <span className="text-xs text-slate-500">
                  {statusLoading ? "Refreshing..." : status.timestamp ? `Updated ${new Date(status.timestamp).toLocaleString()}` : "No timestamp"}
                </span>
              </div>
              <div className="mt-4 space-y-3">
                {status.findings.map((finding) => (
                  <article key={finding.title} className={`rounded-md border p-4 ${statusClass[finding.severity]}`}>
                    <div className="flex items-center justify-between gap-4">
                      <h3 className="font-medium">{finding.title}</h3>
                      <span className="text-xs">{statusLabel[finding.severity]}</span>
                    </div>
                    <p className="mt-2 text-sm text-slate-700">证据：{finding.evidence}</p>
                    <p className="mt-1 text-sm text-slate-700">建议：{finding.recommendation}</p>
                  </article>
                ))}
              </div>
            </section>

            <section className="rounded-md bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-lg font-semibold">节点状态</h2>
                <span className="text-xs text-slate-500">{status.mode === "cluster" ? "Multi-node" : "Local MVP"}</span>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                {nodes.map((node) => (
                  <article key={node.id} className={`rounded-md border p-4 ${statusClass[node.status]}`}>
                    <div className="flex items-center gap-2">
                      <Server size={16} />
                      <h3 className="text-sm font-semibold">{node.id}</h3>
                    </div>
                    <p className="mt-2 text-xs text-slate-600">{node.role}</p>
                    <p className="mt-3 text-sm">{nodeSummary(node)}</p>
                    <p className="mt-3 text-xs text-slate-500">{nodeDetail(node)}</p>
                  </article>
                ))}
              </div>
            </section>
          </section>

          <aside className="rounded-md bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <MessageSquare size={18} />
              <h2 className="text-lg font-semibold">诊断对话</h2>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              消息会通过本地 API channel 进入 Nanobot 的 InboundMessage 流程，再由 Agent 调用 skill、tool 和 memory。
            </p>
            <div className="mt-4 h-[520px] space-y-3 overflow-y-auto rounded-md border border-slate-200 bg-slate-50 p-3">
              {messages.map((message, index) => (
                <div key={`${message.role}-${index}`} className={message.role === "user" ? "flex justify-end" : "flex justify-start"}>
                  <div className={`max-w-[82%] whitespace-pre-wrap rounded-md px-3 py-2 text-sm leading-6 ${
                    message.role === "user" ? "bg-slate-900 text-white" : message.error ? "bg-rose-50 text-rose-900 shadow-sm" : "bg-white text-slate-800 shadow-sm"
                  }`}>
                    <div className="mb-1 flex items-center gap-1 text-xs opacity-70">
                      {message.role === "user" ? <MessageSquare size={12} /> : <Bot size={12} />}
                      {message.role === "user" ? "Operator" : "Ops Agent"}
                    </div>
                    {message.content}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 flex gap-2">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") sendMessage();
                }}
                disabled={isSending}
                className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-700"
                placeholder="例如：帮我执行一次完整巡检"
              />
              <button
                type="button"
                onClick={sendMessage}
                disabled={isSending}
                className="inline-flex h-10 w-10 items-center justify-center rounded-md bg-slate-900 text-white disabled:cursor-not-allowed disabled:bg-slate-400"
                aria-label="Send diagnostic message"
              >
                <Send size={16} />
              </button>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}

function metricIcon(label: string) {
  if (label === "CPU") return <Cpu size={18} />;
  if (label === "内存") return <Activity size={18} />;
  if (label === "磁盘") return <HardDrive size={18} />;
  if (label === "Nanobot") return <ShieldCheck size={18} />;
  return <Network size={18} />;
}

function metricsFromNodes(nodes: ClusterNode[] = []): LocalMetric[] {
  if (!nodes.length) return fallbackMetrics;

  const normalCount = nodes.filter((node) => node.status === "normal").length;
  const warningCount = nodes.filter((node) => node.status === "warning").length;
  const criticalCount = nodes.filter((node) => node.status === "critical").length;
  const remoteCount = nodes.filter((node) => node.type === "ssh").length;
  const gpuCount = nodes.reduce((sum, node) => sum + (node.metrics.gpus?.length || 0), 0);

  return [
    {
      label: "节点",
      value: `${normalCount}/${nodes.length}`,
      status: criticalCount ? "critical" : warningCount ? "warning" : "normal",
      detail: `正常 ${normalCount} 台，关注 ${warningCount} 台，异常 ${criticalCount} 台`,
    },
    {
      label: "远程",
      value: `${remoteCount} 台`,
      status: remoteCount > 0 ? "normal" : "unknown",
      detail: remoteCount > 0 ? "已通过 SSH 接入远程巡检节点" : "暂未接入远程节点",
    },
    {
      label: "GPU",
      value: `${gpuCount} 张`,
      status: gpuCount > 0 ? "normal" : "unknown",
      detail: gpuCount > 0 ? "已检测到 GPU 指标" : "当前节点未检测到 nvidia-smi",
    },
    {
      label: "磁盘",
      value: `${maxMetric(nodes, "diskUsagePercent")}%`,
      status: maxMetric(nodes, "diskUsagePercent") >= 90 ? "critical" : maxMetric(nodes, "diskUsagePercent") >= 80 ? "warning" : "normal",
      detail: "显示所有节点根分区中的最高使用率",
    },
  ];
}

function maxMetric(nodes: ClusterNode[], key: "diskUsagePercent" | "memoryUsagePercent") {
  return Math.max(0, ...nodes.map((node) => Number(node.metrics[key] || 0)));
}

function nodeSummary(node: ClusterNode | ExtensionNode) {
  if ("metrics" in node) {
    const memory = formatPercent(node.metrics.memoryUsagePercent);
    const disk = formatPercent(node.metrics.diskUsagePercent);
    return `内存 ${memory}，磁盘 ${disk}`;
  }

  return node.note;
}

function nodeDetail(node: ClusterNode | ExtensionNode) {
  if ("metrics" in node) {
    const host = node.host || node.metrics.hostname || node.type;
    const gpuText = node.metrics.gpus?.length ? `GPU ${node.metrics.gpus.length} 张` : "未检测到 GPU";
    return `${host} · ${gpuText}`;
  }

  return node.status === "unknown" ? "保留扩展接口，暂未接入真实采集" : statusLabel[node.status];
}

function formatPercent(value?: number) {
  if (typeof value !== "number") return "N/A";
  return `${value.toFixed(1)}%`;
}
