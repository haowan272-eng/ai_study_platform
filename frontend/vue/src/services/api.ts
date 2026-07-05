export type LearningTask = {
  week?: number;
  topic?: string;
  outcome?: string;
  hours?: number;
  intent?: string;
  query?: string;
  key_points?: string[];
  practice?: string;
  status?: string;
};

export type Resource = {
  name?: string;
  url?: string;
  description?: string;
  stars?: number;
  language?: string;
  topics?: string[];
  updated_at?: string;
  search_queries?: string[];
  source?: string;
};

export type ProjectTask = {
  title?: string;
  objective?: string;
  github_references?: Array<{ repo?: string; takeaway?: string }>;
  milestones?: string[];
  technical_requirements?: string[];
  deliverables?: string[];
  acceptance_criteria?: string[];
  stretch_goals?: string[];
  estimated_hours?: number;
};

export type TutorTask = {
  title?: string;
  objective?: string;
  concepts?: string[];
  example?: string;
  practice_steps?: string[];
  common_mistakes?: string[];
  learning_links?: Array<{ title?: string; url?: string; description?: string }>;
};

export type QuizQuestion = {
  id: number;
  question: string;
  options: string[];
  topic?: string;
  correct_answer?: string;
  explanation?: string;
  user_answer?: string;
  is_correct?: boolean;
};

export type InterviewQuestion = {
  question?: string;
  reference_answer?: string;
  follow_up?: string;
};

export type InterviewEvaluation = {
  question?: string;
  answer?: string;
  score?: number;
  feedback?: string;
  strengths?: string[];
  improvements?: string[];
};

export type AgentError = {
  node?: string;
  error_type?: string;
  message?: string;
  retryable?: boolean;
};

export type CoachState = {
  current_task_id?: string;
  pause_requested?: boolean;
  last_checkpoint_node?: string;
  checkpoint_step?: number;
  user_goal?: string;
  plan_only?: boolean;
  current_topic?: string;
  current_week?: number;
  completed_weeks?: number[];
  learning_plan?: LearningTask[];
  tutor_content?: string;
  tutor_task?: TutorTask;
  resources?: Resource[];
  repo_analysis?: Array<Record<string, unknown>>;
  project_task?: ProjectTask;
  learning_report?: string;
  quiz?: QuizQuestion[];
  score?: number | null;
  weak_points?: string[];
  interview_questions?: InterviewQuestion[];
  interview_answers?: string[];
  interview_evaluations?: InterviewEvaluation[];
  interview_score?: number | null;
  completed_agents?: string[];
  errors?: AgentError[];
  failed_node?: string | null;
  status?: string;
  next_action?: string;
};

export type CoachResponse = {
  session_id: string;
  state: CoachState;
};

export type SessionSummary = {
  session_id: string;
  user_goal?: string;
  current_topic?: string | null;
  status?: string;
  score?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type StreamAgentEvent = {
  session_id: string;
  agent?: string;
  status?: string;
  next_action?: string;
  completed_agents?: string[];
  message?: string;
  state?: CoachState;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

const API_BASE = import.meta.env.VITE_API_BASE?.replace(/\/$/, "") ?? "";

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

function detailToText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) return String(item.msg);
        return JSON.stringify(item);
      })
      .join("; ");
  }
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return "";
}

export async function parseApiError(response: Response): Promise<string> {
  let raw = "";
  try {
    raw = await response.text();
    const data = raw ? JSON.parse(raw) : {};
    const detail = detailToText(data.detail ?? data.message ?? data.error);
    if (detail) return detail;
  } catch {
    if (raw) return raw;
  }

  if (response.status === 400) return "请求参数有误，请检查输入。";
  if (response.status === 401) return "登录已过期或无效，请重新登录。";
  if (response.status === 403) return "你没有权限访问这份数据。";
  if (response.status === 404) return "请求的数据不存在，或不属于当前用户。";
  if (response.status === 409) return "当前状态不允许执行这个操作。";
  if (response.status >= 500) return "后端服务错误，请查看后端日志。";
  return `请求失败（HTTP ${response.status}）。`;
}

function normalizeAuthError(message: string, action: "login" | "register") {
  const lower = message.toLowerCase();
  if (message === "Not Found" || lower.includes("not found")) {
    return action === "login" ? "用户不存在，请先注册。" : "认证接口不可用，请重启后端。";
  }
  if (action === "login" && lower.includes("invalid")) return "登录失败，请检查用户名和密码。";
  if (action === "register" && lower.includes("already exists")) return "用户名已存在，请换一个用户名或直接登录。";
  return message;
}

export function messageFromError(exc: unknown, fallback: string): string {
  if (exc instanceof Error && exc.message) return exc.message;
  if (typeof exc === "string" && exc) return exc;
  return fallback;
}

async function requestJson<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...authHeaders(token),
        ...(init.headers ?? {})
      }
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    return response.json();
  } catch (exc) {
    if (exc instanceof TypeError) throw new Error("无法连接后端，请检查服务和端口。");
    throw exc;
  }
}

export async function login(username: string, password: string): Promise<TokenResponse> {
  try {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    if (!response.ok) throw new Error(normalizeAuthError(await parseApiError(response), "login"));
    return response.json();
  } catch (exc) {
    if (exc instanceof TypeError) throw new Error("无法连接后端，请先启动后端服务。");
    throw exc;
  }
}

export async function register(username: string, password: string) {
  try {
    const response = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    if (!response.ok) throw new Error(normalizeAuthError(await parseApiError(response), "register"));
    return response.json();
  } catch (exc) {
    if (exc instanceof TypeError) throw new Error("无法连接后端，请先启动后端服务。");
    throw exc;
  }
}

export async function verifySession(token: string) {
  const response = await fetch(`${API_BASE}/auth/me`, {
    headers: authHeaders(token)
  });
  if (!response.ok) throw new Error(await parseApiError(response));
  return response.json();
}

export async function getLatestLearningSession(token: string): Promise<CoachResponse> {
  return requestJson("/learning-coach/sessions/latest", token);
}

export async function listLearningSessions(token: string): Promise<{ sessions: SessionSummary[] }> {
  return requestJson("/learning-coach/sessions", token);
}

export function openLearningEvents(sessionId: string, token: string): EventSource {
  const params = new URLSearchParams({ access_token: token });
  return new EventSource(`${API_BASE}/learning-coach/${sessionId}/events?${params.toString()}`);
}

export async function startLearning(userGoal: string, token: string): Promise<CoachResponse> {
  return requestJson("/learning-coach/start", token, {
    method: "POST",
    body: JSON.stringify({ user_goal: userGoal })
  });
}

export async function startWeek(sessionId: string, week: number, token: string): Promise<CoachResponse> {
  return requestJson(`/learning-coach/${sessionId}/weeks/${week}/start`, token, { method: "POST" });
}

export async function pauseLearningTask(sessionId: string, token: string): Promise<CoachResponse> {
  return requestJson(`/learning-coach/${sessionId}/pause`, token, { method: "POST" });
}

export async function resumeLearningTask(sessionId: string, token: string): Promise<CoachResponse> {
  return requestJson(`/learning-coach/${sessionId}/resume`, token, { method: "POST" });
}

export async function completeWeek(sessionId: string, week: number, token: string): Promise<CoachResponse> {
  return requestJson(`/learning-coach/${sessionId}/weeks/${week}/complete`, token, { method: "POST" });
}

export async function submitQuiz(sessionId: string, answers: string[], token: string): Promise<CoachResponse> {
  return requestJson(`/learning-coach/${sessionId}/submit`, token, {
    method: "POST",
    body: JSON.stringify({ answers })
  });
}

export async function submitInterview(sessionId: string, answers: string[], token: string): Promise<CoachResponse> {
  return requestJson(`/learning-coach/${sessionId}/interview/submit`, token, {
    method: "POST",
    body: JSON.stringify({ answers })
  });
}
