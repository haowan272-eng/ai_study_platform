<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import type { CoachState, InterviewQuestion, LearningTask, StreamAgentEvent } from "./services/api";
import {
  completeWeek,
  getLatestLearningSession,
  login,
  messageFromError,
  openLearningEvents,
  pauseLearningTask,
  register,
  resumeLearningTask,
  startLearning,
  startWeek,
  submitInterview,
  submitQuiz
} from "./services/api";

const defaultGoal = "学习 LangGraph 和 MCP，并完成一个可放入作品集的多智能体项目。";
const username = ref(localStorage.getItem("coach_username") ?? "");
const password = ref("");
const accessToken = ref(localStorage.getItem("coach_access_token") ?? "");
const authMode = ref<"login" | "register">("login");
const userGoal = ref(defaultGoal);
const learnerId = ref(username.value || "anonymous");
const sessionId = ref("");
const state = ref<CoachState>({});
const events = ref<StreamAgentEvent[]>([]);
const loading = ref(false);
const taskControlBusy = ref(false);
const showFinalQuizCongrats = ref(false);
const awaitingFinalQuizCongrats = ref(false);
const notice = ref("");
const answers = reactive<Record<number, string>>({});
const interviewAnswers = reactive<Record<number, string>>({});
const revealedAnswers = reactive<Record<number, boolean>>({});
const errors = reactive<Record<string, string>>({
  auth: "",
  route: "",
  week: "",
  quiz: "",
  session: ""
});
const collapsed = reactive<Record<string, boolean>>({
  events: false,
  route: false,
  tutor: false,
  resources: false,
  project: false,
  report: true,
  quiz: false,
  interview: false
});

const agentLabels: Record<string, string> = {
  supervisor: "调度器",
  planner: "规划助手",
  tutor: "学习导师",
  opensource_mentor: "开源导师",
  reporter: "学习报告",
  assessment: "测评助手",
  interview: "面试官",
  session: "会话"
};

const statusLabels: Record<string, string> = {
  pending: "待开始",
  active: "进行中",
  completed: "已完成",
  started: "已开始",
  planning_completed: "路线已生成",
  week_started: "本周已开始",
  tutoring_completed: "学习内容已生成",
  remediation_completed: "补弱内容已生成",
  resources_and_project_completed: "开源资料与项目任务已生成",
  report_completed: "报告已生成",
  awaiting_answers: "等待提交测验",
  assessment_passed: "测验通过",
  assessment_failed: "测验未通过",
  interview_reviewed: "面试已评分",
  course_completed: "课程已完成",
  restored: "已恢复",
  pausing: "暂停中",
  paused: "已暂停"
};

const nextActionLabels: Record<string, string> = {
  select_week: "选择一周开始",
  tutor: "生成学习内容",
  opensource_mentor: "搜索开源项目",
  reporter: "生成学习报告",
  assessment: "生成或评分测验",
  interview: "生成面试题",
  submit_quiz: "提交测验",
  review_weak_points_and_retry: "复习薄弱点并重测",
  interview_and_build_project: "完成面试与项目",
  all_weeks_completed: "所有学习周已完成",
  supervisor: "路由判断",
  pause_after_checkpoint: "暂停到下一个检查点",
  resume_task: "继续执行任务"
};

const isAuthed = computed(() => Boolean(accessToken.value));
const completedAgents = computed(() => new Set(state.value.completed_agents ?? []));
const completedWeeks = computed(() => new Set(state.value.completed_weeks ?? []));
const quiz = computed(() => state.value.quiz ?? []);
const hasWeekContent = computed(() => !state.value.plan_only && Boolean(state.value.current_topic));
const quizPassed = computed(() => hasQuizResult() && Number(state.value.score) >= 60);
const quizFailed = computed(() => hasQuizResult() && Number(state.value.score) < 60);
const pausableStatuses = new Set(["queued", "running"]);
const resumableStatuses = new Set(["paused"]);
const canToggleTaskRun = computed(() => {
  const status = state.value.status ?? "";
  return Boolean(sessionId.value && (pausableStatuses.has(status) || resumableStatuses.has(status) || status === "pausing"));
});
const taskToggleLabel = computed(() => {
  if (state.value.status === "paused") return "继续";
  if (state.value.status === "pausing") return "暂停中...";
  return "暂停";
});
const taskToggleDisabled = computed(() => taskControlBusy.value || state.value.status === "pausing");
let eventSource: EventSource | null = null;

const terminalStatuses = new Set([
  "planning_completed",
  "completed",
  "remediation_completed",
  "awaiting_answers",
  "assessment_failed",
  "interview_reviewed",
  "course_completed",
  "failed",
  "failed_report_completed",
  "paused"
]);

function clearErrors(...keys: string[]) {
  for (const key of keys) errors[key] = "";
}

function setError(key: string, exc: unknown, fallback: string) {
  errors[key] = messageFromError(exc, fallback);
}

function labelStatus(value?: string) {
  return value ? statusLabels[value] ?? value : "未开始";
}

function labelNextAction(value?: string) {
  return value ? nextActionLabels[value] ?? value : "-";
}

function eventText(event: StreamAgentEvent) {
  if (event.status) return labelStatus(event.status);
  if (event.message) return event.message;
  if (event.next_action) return labelNextAction(event.next_action);
  return "运行中";
}

function toggle(key: string) {
  collapsed[key] = !collapsed[key];
}

function resetAnswers() {
  for (const key of Object.keys(answers)) delete answers[Number(key)];
  for (const key of Object.keys(interviewAnswers)) delete interviewAnswers[Number(key)];
  for (const key of Object.keys(revealedAnswers)) delete revealedAnswers[Number(key)];
}

function hydrateInputs(nextState: CoachState) {
  resetAnswers();
  for (const question of nextState.quiz ?? []) {
    if (question.user_answer) answers[question.id] = question.user_answer;
  }
  for (const [index, answer] of (nextState.interview_answers ?? []).entries()) {
    if (answer) interviewAnswers[index] = answer;
  }
}

function isFinalWeekState(nextState: CoachState) {
  const weeks = (nextState.learning_plan ?? [])
    .map((task) => Number(task.week ?? 0))
    .filter((week) => week > 0);
  const lastWeek = weeks.length ? Math.max(...weeks) : 0;
  return Boolean(lastWeek && Number(nextState.current_week ?? 0) === lastWeek);
}

function maybeShowFinalQuizCongrats(nextState: CoachState) {
  if (!awaitingFinalQuizCongrats.value) return;
  const passed = nextState.score !== null && nextState.score !== undefined && Number(nextState.score) >= 60;
  if (passed && isFinalWeekState(nextState)) {
    showFinalQuizCongrats.value = true;
    awaitingFinalQuizCongrats.value = false;
  } else if (nextState.score !== null && nextState.score !== undefined) {
    awaitingFinalQuizCongrats.value = false;
  }
}

function setCoachState(nextState: CoachState) {
  state.value = nextState;
  if (nextState.user_goal) userGoal.value = nextState.user_goal;
  hydrateInputs(nextState);
  maybeShowFinalQuizCongrats(nextState);
}

function applyStreamEvent(event: StreamAgentEvent) {
  events.value.push(event);
  if (event.state) setCoachState(event.state);
}

function closeEventStream() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function isTerminalStatus(status?: string) {
  return Boolean(status && terminalStatuses.has(status));
}

function appendProgressEvent(result: { session_id: string; state: CoachState }, message?: string) {
  const current = result.state;
  const previous = events.value[events.value.length - 1];
  const completed = current.completed_agents ?? [];
  const agent = completed[completed.length - 1] ?? "session";
  if (
    previous?.status === current.status &&
    previous?.next_action === current.next_action &&
    previous?.completed_agents?.join("|") === completed.join("|")
  ) {
    return;
  }
  events.value.push({
    session_id: result.session_id,
    agent,
    status: current.status,
    next_action: current.next_action,
    completed_agents: completed,
    message,
    state: current
  });
}

function connectEventStream(targetSessionId: string, errorKey: string) {
  closeEventStream();
  eventSource = openLearningEvents(targetSessionId, accessToken.value);
  eventSource.onmessage = (rawEvent) => {
    try {
      const event = JSON.parse(rawEvent.data) as StreamAgentEvent;
      applyStreamEvent(event);
      if (event.state && isTerminalStatus(event.state.status)) {
        loading.value = false;
        closeEventStream();
      }
    } catch (exc) {
      loading.value = false;
      closeEventStream();
      setError(errorKey, exc, "实时进度解析失败。");
    }
  };
  eventSource.onerror = () => {
    loading.value = false;
    closeEventStream();
    setError(errorKey, new Error("实时进度连接已断开。"), "实时进度连接已断开。");
  };
}

async function toggleTaskRun() {
  if (!sessionId.value || !accessToken.value || taskToggleDisabled.value) return;
  taskControlBusy.value = true;
  clearErrors("session", "route", "week", "quiz");
  try {
    const result =
      state.value.status === "paused"
        ? await resumeLearningTask(sessionId.value, accessToken.value)
        : await pauseLearningTask(sessionId.value, accessToken.value);
    setCoachState(result.state);
    appendProgressEvent(result, state.value.status === "paused" ? "任务已暂停" : "任务状态已更新");
    if (!isTerminalStatus(result.state.status)) {
      loading.value = true;
      connectEventStream(result.session_id, "session");
    } else {
      loading.value = false;
      closeEventStream();
    }
  } catch (exc) {
    setError("session", exc, state.value.status === "paused" ? "继续任务失败。" : "暂停任务失败。");
  } finally {
    taskControlBusy.value = false;
  }
}

async function restoreLatestSession(token = accessToken.value, silent = false) {
  if (!token) return;
  let shouldKeepStream = false;
  try {
    if (!silent) loading.value = true;
    clearErrors("route", "week", "quiz", "session");
    const result = await getLatestLearningSession(token);
    sessionId.value = result.session_id;
    setCoachState(result.state);
    events.value = [
      {
        session_id: result.session_id,
        agent: "session",
        status: "restored",
        message: "已恢复上次学习记录"
      }
    ];
    shouldKeepStream = !isTerminalStatus(result.state.status);
    if (shouldKeepStream) connectEventStream(result.session_id, "session");
  } catch (exc) {
    const message = messageFromError(exc, "");
    if (!message.includes("还没有学习记录") && !message.includes("不存在")) {
      if (!silent) errors.route = message || "恢复上次学习记录失败。";
    }
  } finally {
    if (!silent) loading.value = shouldKeepStream;
  }
}

async function handleAuth() {
  if (!username.value.trim()) {
    errors.auth = "请输入用户名。";
    return;
  }
  if (!password.value) {
    errors.auth = "请输入密码。";
    return;
  }
  if (loading.value) return;
  try {
    loading.value = true;
    notice.value = "";
    clearErrors("auth");
    if (authMode.value === "register") {
      await register(username.value.trim(), password.value);
      authMode.value = "login";
      password.value = "";
      notice.value = "注册成功，请登录。";
      return;
    }
    const tokens = await login(username.value.trim(), password.value);
    accessToken.value = tokens.access_token;
    localStorage.setItem("coach_access_token", tokens.access_token);
    localStorage.setItem("coach_refresh_token", tokens.refresh_token);
    localStorage.setItem("coach_username", username.value.trim());
    learnerId.value = username.value.trim();
    password.value = "";
    await restoreLatestSession(tokens.access_token, true);
  } catch (exc) {
    setError("auth", exc, authMode.value === "register" ? "注册失败。" : "登录失败。");
  } finally {
    loading.value = false;
  }
}

function logout() {
  closeEventStream();
  accessToken.value = "";
  localStorage.removeItem("coach_access_token");
  localStorage.removeItem("coach_refresh_token");
  localStorage.removeItem("coach_username");
  sessionId.value = "";
  state.value = {};
  events.value = [];
  resetAnswers();
  clearErrors("auth", "route", "week", "quiz", "session");
}

async function start() {
  if (!accessToken.value) {
    errors.route = "请先登录。";
    return;
  }
  if (!userGoal.value.trim()) {
    errors.route = "请输入学习目标。";
    return;
  }
  if (loading.value) return;
  closeEventStream();
  loading.value = true;
  sessionId.value = "";
  state.value = {};
  events.value = [];
  resetAnswers();
  clearErrors("route", "week", "quiz", "session");

  try {
    const result = await startLearning(userGoal.value.trim(), learnerId.value.trim() || username.value, accessToken.value);
    sessionId.value = result.session_id;
    setCoachState(result.state);
    appendProgressEvent(result, "后台任务已创建");
    connectEventStream(result.session_id, "route");
  } catch (exc) {
    loading.value = false;
    setError("route", exc, "创建学习任务失败。");
  }
}

function hasQuizResult() {
  return state.value.score !== null && state.value.score !== undefined;
}

function optionState(question: { correct_answer?: string; user_answer?: string }, option: string) {
  if (!hasQuizResult()) return "";
  if (option === question.correct_answer) return "correct";
  if (option === question.user_answer && option !== question.correct_answer) return "wrong";
  return "";
}

function retryQuiz() {
  for (const key of Object.keys(answers)) delete answers[Number(key)];
  awaitingFinalQuizCongrats.value = false;
  state.value = {
    ...state.value,
    quiz: quiz.value.map(({ correct_answer, user_answer, is_correct, ...question }) => question),
    score: null,
    interview_questions: [],
    interview_answers: [],
    interview_evaluations: [],
    interview_score: null
  };
  clearErrors("quiz", "week", "session");
}

function taskState(task: LearningTask) {
  if (task.week && completedWeeks.value.has(task.week)) return "completed";
  if (!state.value.plan_only && task.week === state.value.current_week) return "active";
  return task.status ?? "pending";
}

async function openWeek(week?: number) {
  if (!sessionId.value) {
    errors.week = "请先生成学习路线。";
    return;
  }
  if (!week) {
    errors.week = "无效的学习周。";
    return;
  }
  if (!accessToken.value) {
    errors.week = "登录已过期，请重新登录。";
    return;
  }
  if (loading.value) return;
  loading.value = true;
  resetAnswers();
  clearErrors("week", "quiz");

  try {
    const result = await startWeek(sessionId.value, week, accessToken.value);
    setCoachState(result.state);
    appendProgressEvent(result, "本周后台任务已创建");
    connectEventStream(result.session_id, "week");
  } catch (exc) {
    loading.value = false;
    setError("week", exc, "开始本周学习失败。");
  }
}

async function finishCurrentWeek() {
  if (!sessionId.value || !state.value.current_week) {
    errors.week = "当前没有正在学习的周。";
    return;
  }
  if (!hasQuizResult()) {
    errors.week = "请先提交并完成本周测验。";
    return;
  }
  if (!quizPassed.value) {
    errors.week = "请先复习薄弱点并通过测验，再进入下一周。";
    return;
  }
  try {
    loading.value = true;
    clearErrors("week", "quiz");
    const result = await completeWeek(sessionId.value, state.value.current_week, accessToken.value);
    setCoachState(result.state);
    resetAnswers();
    appendProgressEvent(result, "background task queued");
    if (!isTerminalStatus(result.state.status)) connectEventStream(result.session_id, "week");
  } catch (exc) {
    setError("week", exc, "完成本周失败。");
  } finally {
    loading.value = false;
  }
}

async function gradeQuiz() {
  if (!sessionId.value) {
    errors.quiz = "请先生成学习路线并进入某一周。";
    return;
  }
  if (!quiz.value.length) {
    errors.quiz = "当前还没有生成测验题。";
    return;
  }
  const unanswered = quiz.value.filter((item) => !answers[item.id]);
  if (unanswered.length) {
    errors.quiz = `还有 ${unanswered.length} 道题未作答。`;
    return;
  }
  try {
    loading.value = true;
    clearErrors("quiz", "week");
    awaitingFinalQuizCongrats.value = isFinalWeekState(state.value);
    showFinalQuizCongrats.value = false;
    const orderedAnswers = quiz.value.map((item) => answers[item.id] ?? "");
    const result = await submitQuiz(sessionId.value, orderedAnswers, accessToken.value);
    setCoachState(result.state);
    appendProgressEvent(result, "background task queued");
    connectEventStream(result.session_id, "quiz");
  } catch (exc) {
    setError("quiz", exc, "提交测验失败。");
  } finally {
    loading.value = false;
  }
}

async function gradeInterview() {
  if (!sessionId.value) {
    errors.session = "请先生成学习会话。";
    return;
  }
  const questions = state.value.interview_questions ?? [];
  if (!questions.length) {
    errors.session = "当前还没有生成面试题。";
    return;
  }
  const missing = questions.filter((_, index) => !interviewAnswers[index]?.trim());
  if (missing.length) {
    errors.session = `还有 ${missing.length} 道面试题未作答。`;
    return;
  }
  try {
    loading.value = true;
    clearErrors("session");
    const orderedAnswers = questions.map((_, index) => interviewAnswers[index] ?? "");
    const result = await submitInterview(sessionId.value, orderedAnswers, accessToken.value);
    setCoachState(result.state);
  } catch (exc) {
    setError("session", exc, "面试答案评分失败。");
  } finally {
    loading.value = false;
  }
}

function toggleReferenceAnswer(index: number) {
  revealedAnswers[index] = !revealedAnswers[index];
}

function hasReferenceAnswer(item: InterviewQuestion) {
  return Boolean(item.reference_answer || item.follow_up);
}

onMounted(() => {
  if (accessToken.value) {
    restoreLatestSession(accessToken.value, true);
  }
});

onUnmounted(() => {
  closeEventStream();
});
</script>

<template>
  <main class="shell">
    <section v-if="!isAuthed" class="auth-shell">
      <div class="auth-panel">
        <p class="eyebrow">AI Agent 学习教练</p>
        <h1>{{ authMode === "login" ? "登录" : "注册" }}</h1>
        <label>
          用户名
          <input v-model="username" autocomplete="username" />
        </label>
        <label>
          密码
          <input v-model="password" type="password" autocomplete="current-password" />
        </label>
        <button :disabled="loading" @click="handleAuth">
          {{ loading ? "处理中..." : authMode === "login" ? "登录" : "注册" }}
        </button>
        <button class="secondary" type="button" @click="authMode = authMode === 'login' ? 'register' : 'login'">
          {{ authMode === "login" ? "没有账号？去注册" : "已有账号？去登录" }}
        </button>
        <p class="success" v-if="notice">{{ notice }}</p>
        <p class="error" v-if="errors.auth">{{ errors.auth }}</p>
      </div>
    </section>

    <template v-else>
      <section class="toolbar">
        <div>
          <p class="eyebrow">AI Agent 学习教练</p>
          <h1>学习路线、每周实战、开源参考与测评闭环</h1>
        </div>
        <div class="session">
          {{ username }}
          <button class="secondary" type="button" @click="logout">退出登录</button>
        </div>
      </section>

      <section class="workspace">
        <aside class="panel control-panel">
          <label>
            学习目标
            <textarea v-model="userGoal" rows="6" />
          </label>
          <button :disabled="loading" @click="start">
            {{ loading ? "生成中..." : "重新生成学习路线" }}
          </button>
          <button class="secondary" type="button" :disabled="loading" @click="restoreLatestSession()">
            恢复上次记录
          </button>
          <p class="error" v-if="errors.route">{{ errors.route }}</p>

          <div class="timeline">
            <div class="section-title compact" @click="toggle('events')">
              <h2>实时进度</h2>
              <button class="secondary" type="button">{{ collapsed.events ? "展开" : "收起" }}</button>
            </div>
            <div v-show="!collapsed.events">
              <div v-if="!events.length" class="empty">等待开始</div>
              <article v-for="(event, index) in events" :key="index" class="event-row">
                <span>{{ agentLabels[event.agent ?? ""] ?? event.agent }}</span>
                <strong>{{ eventText(event) }}</strong>
              </article>
            </div>
          </div>
        </aside>

        <section class="content">
          <div class="status-strip">
            <span>状态：{{ labelStatus(state.status) }}</span>
            <span>周次：{{ hasWeekContent ? `第 ${state.current_week} 周` : "请选择周次" }}</span>
            <span>主题：{{ state.current_topic ?? "-" }}</span>
            <span>下一步：{{ labelNextAction(state.next_action) }}</span>
            <button
              v-if="canToggleTaskRun"
              class="status-action"
              type="button"
              :disabled="taskToggleDisabled"
              @click="toggleTaskRun"
            >
              {{ taskToggleLabel }}
            </button>
          </div>

          <section class="panel">
            <div class="section-title" @click="toggle('route')">
              <h2>学习路线</h2>
              <span>{{ state.learning_plan?.length ?? 0 }} 个阶段</span>
              <button class="secondary" type="button">{{ collapsed.route ? "展开" : "收起" }}</button>
            </div>
            <p class="error" v-if="errors.week">{{ errors.week }}</p>
            <div v-show="!collapsed.route" class="task-grid">
              <article
                v-for="task in state.learning_plan ?? []"
                :key="task.week"
                class="task-card"
                :class="taskState(task)"
              >
                <div class="task-head">
                  <div class="week">第 {{ task.week }} 周</div>
                  <span>{{ labelStatus(taskState(task)) }}</span>
                </div>
                <h3>{{ task.topic }}</h3>
                <p>{{ task.intent }}</p>
                <ul>
                  <li v-for="point in task.key_points ?? []" :key="point">{{ point }}</li>
                </ul>
                <footer>{{ task.practice }}</footer>
                <div class="task-actions">
                  <button
                    v-if="state.plan_only || task.week !== state.current_week"
                    :disabled="loading"
                    @click.stop="openWeek(task.week)"
                  >
                    开始本周
                  </button>
                  <button
                    v-else
                    :disabled="loading || !quizPassed"
                    @click.stop="finishCurrentWeek"
                  >
                    完成本周并继续
                  </button>
                </div>
              </article>
            </div>
          </section>

          <section class="panel" v-if="hasWeekContent && (state.tutor_task || state.tutor_content)">
            <div class="section-title" @click="toggle('tutor')">
              <h2>本周学习内容</h2>
              <span>第 {{ state.current_week }} 周</span>
              <button class="secondary" type="button">{{ collapsed.tutor ? "展开" : "收起" }}</button>
            </div>
            <div v-show="!collapsed.tutor">
              <h3>{{ state.tutor_task?.title ?? state.current_topic }}</h3>
              <p>{{ state.tutor_task?.objective ?? state.tutor_content }}</p>

              <h4 v-if="state.tutor_task?.concepts?.length">核心概念</h4>
              <ul>
                <li v-for="concept in state.tutor_task?.concepts ?? []" :key="concept">{{ concept }}</li>
              </ul>

              <h4 v-if="state.tutor_task?.example">示例</h4>
              <pre v-if="state.tutor_task?.example" class="markdown">{{ state.tutor_task.example }}</pre>

              <h4 v-if="state.tutor_task?.practice_steps?.length">实践步骤</h4>
              <ol>
                <li v-for="step in state.tutor_task?.practice_steps ?? []" :key="step">{{ step }}</li>
              </ol>

              <h4 v-if="state.tutor_task?.common_mistakes?.length">常见误区</h4>
              <ul>
                <li v-for="mistake in state.tutor_task?.common_mistakes ?? []" :key="mistake">{{ mistake }}</li>
              </ul>

              <h4 v-if="state.tutor_task?.learning_links?.length">学习视频与资料链接</h4>
              <article v-for="link in state.tutor_task?.learning_links ?? []" :key="link.url" class="repo-row">
                <a :href="link.url" target="_blank" rel="noreferrer">{{ link.title }}</a>
                <p>{{ link.description }}</p>
              </article>
            </div>
          </section>

          <section class="split" v-if="hasWeekContent">
            <div class="panel">
              <div class="section-title" @click="toggle('resources')">
                <h2>GitHub 开源推荐</h2>
                <span>{{ state.resources?.length ?? 0 }} 个仓库</span>
                <button class="secondary" type="button">{{ collapsed.resources ? "展开" : "收起" }}</button>
              </div>
              <div v-show="!collapsed.resources">
                <article v-for="repo in state.resources ?? []" :key="repo.url" class="repo-row">
                  <a :href="repo.url" target="_blank" rel="noreferrer">{{ repo.name }}</a>
                  <span>{{ repo.language ?? "未知语言" }} - {{ repo.stars ?? 0 }} stars</span>
                  <small v-if="repo.source === 'fallback'" class="repo-source">内置参考</small>
                  <p>{{ repo.description }}</p>
                  <div class="repo-meta" v-if="repo.search_queries?.length">
                    搜索关键词：{{ repo.search_queries.slice(0, 2).join(" / ") }}
                  </div>
                </article>
              </div>
            </div>

            <div class="panel">
              <div class="section-title" @click="toggle('project')">
                <h2>作品集实战任务</h2>
                <span>{{ state.project_task?.estimated_hours ?? "-" }} 小时</span>
                <button class="secondary" type="button">{{ collapsed.project ? "展开" : "收起" }}</button>
              </div>
              <div v-show="!collapsed.project">
                <h3>{{ state.project_task?.title }}</h3>
                <p>{{ state.project_task?.objective }}</p>
                <ol>
                  <li v-for="milestone in state.project_task?.milestones ?? []" :key="milestone">
                    {{ milestone }}
                  </li>
                </ol>
              </div>
            </div>
          </section>

          <section class="panel" v-if="hasWeekContent && state.learning_report">
            <div class="section-title" @click="toggle('report')">
              <h2>学习报告</h2>
              <span :class="{ done: completedAgents.has('reporter') }">报告已生成</span>
              <button class="secondary" type="button">{{ collapsed.report ? "展开" : "收起" }}</button>
            </div>
            <pre v-show="!collapsed.report" class="markdown">{{ state.learning_report }}</pre>
          </section>

          <section class="panel" v-if="hasWeekContent && quiz.length">
            <div class="section-title" @click="toggle('quiz')">
              <h2>阶段测验</h2>
              <span v-if="hasQuizResult()">得分 {{ state.score }}</span>
              <button class="secondary" type="button">{{ collapsed.quiz ? "展开" : "收起" }}</button>
            </div>
            <p class="error" v-if="errors.quiz">{{ errors.quiz }}</p>
            <div v-show="!collapsed.quiz">
              <div v-if="quizFailed" class="warning">
                <strong>测验暂未通过。</strong>
                <p>请先复习薄弱点和补弱学习内容，再重新作答提交。</p>
              </div>
              <div v-else-if="quizPassed" class="success">
                <strong>测验已通过。</strong>
                <p>你可以继续完成模拟面试，并在复盘后进入下一周。</p>
              </div>
              <div v-for="question in quiz" :key="question.id" class="question">
                <h3>{{ question.id }}. {{ question.question }}</h3>
                <label
                  v-for="option in question.options"
                  :key="option"
                  class="option"
                  :class="optionState(question, option)"
                >
                  <input
                    type="radio"
                    :name="`q-${question.id}`"
                    :value="option"
                    v-model="answers[question.id]"
                    :disabled="hasQuizResult() && !quizFailed"
                  />
                  {{ option }}
                </label>
                <div v-if="hasQuizResult()" class="reference-answer">
                  <strong>正确答案：{{ question.correct_answer }}</strong>
                  <p v-if="question.explanation">解析：{{ question.explanation }}</p>
                </div>
              </div>
              <button v-if="!hasQuizResult()" :disabled="loading" @click="gradeQuiz">
                提交测验
              </button>
              <button v-else-if="quizFailed" :disabled="loading" @click="retryQuiz">
                重新作答
              </button>
              <p v-if="state.weak_points?.length" class="warning">
                薄弱点：{{ state.weak_points.join("、") }}
              </p>
            </div>
          </section>

          <section class="panel" v-if="hasWeekContent && quizPassed && state.interview_questions?.length">
            <div class="section-title" @click="toggle('interview')">
              <h2>模拟面试</h2>
              <span v-if="state.interview_score !== null && state.interview_score !== undefined">
                得分 {{ state.interview_score }}
              </span>
              <span v-else>测验通过后生成</span>
              <button class="secondary" type="button">{{ collapsed.interview ? "展开" : "收起" }}</button>
            </div>
            <p class="error" v-if="errors.session">{{ errors.session }}</p>
            <div v-show="!collapsed.interview">
              <article v-for="(item, index) in state.interview_questions" :key="item.question" class="interview">
                <h3>{{ item.question }}</h3>
                <label>
                  你的回答
                  <textarea
                    v-model="interviewAnswers[index]"
                    rows="4"
                    :disabled="Boolean(state.interview_evaluations?.[index])"
                    placeholder="请结合架构选择、技术取舍和你的项目例子作答。"
                  />
                </label>

                <div v-if="state.interview_evaluations?.[index]" class="reference-answer">
                  <strong>得分：{{ state.interview_evaluations[index].score }}</strong>
                  <p>{{ state.interview_evaluations[index].feedback }}</p>
                  <div v-if="state.interview_evaluations[index].strengths?.length">
                    <strong>亮点</strong>
                    <ul>
                      <li v-for="point in state.interview_evaluations[index].strengths" :key="point">{{ point }}</li>
                    </ul>
                  </div>
                  <div v-if="state.interview_evaluations[index].improvements?.length">
                    <strong>改进建议</strong>
                    <ul>
                      <li v-for="point in state.interview_evaluations[index].improvements" :key="point">{{ point }}</li>
                    </ul>
                  </div>
                </div>

                <button
                  v-if="state.interview_evaluations?.[index] && hasReferenceAnswer(item)"
                  class="secondary"
                  type="button"
                  @click="toggleReferenceAnswer(index)"
                >
                  {{ revealedAnswers[index] ? "隐藏参考答案" : "查看参考答案" }}
                </button>
                <div v-if="revealedAnswers[index]" class="reference-answer">
                  <strong>参考答案</strong>
                  <p>{{ item.reference_answer }}</p>
                  <small v-if="item.follow_up">追问：{{ item.follow_up }}</small>
                </div>
              </article>
              <button
                v-if="!state.interview_evaluations?.length"
                :disabled="loading"
                @click="gradeInterview"
              >
                提交面试答案
              </button>
            </div>
          </section>
        </section>
      </section>
    </template>

    <div v-if="showFinalQuizCongrats" class="modal-backdrop">
      <section class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="final-quiz-title">
        <h2 id="final-quiz-title">恭喜你，通过测验！</h2>
        <p>你已完成本阶段学习，并顺利通过本次测验。</p>
        <button type="button" @click="showFinalQuizCongrats = false">关闭</button>
      </section>
    </div>
  </main>
</template>
