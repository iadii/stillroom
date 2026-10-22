<script setup>
import { computed, onMounted, ref } from "vue";
import { displayDate, request } from "./api";
import DocumentDetail from "./components/DocumentDetail.vue";
import DocumentRow from "./components/DocumentRow.vue";
import UploadPanel from "./components/UploadPanel.vue";

const view = ref("overview");
const documents = ref([]);
const events = ref([]);
const stats = ref({ total: 0, inbox: 0, ready: 0, approved: 0, archived: 0 });
const groqReady = ref(false);
const selectedId = ref(null);
const search = ref("");
const busy = ref(false);
const progress = ref("");
const notice = ref("");
const isError = ref(false);

const inbox = computed(() =>
  documents.value.filter((doc) => doc.state !== "archived"),
);
const archive = computed(() =>
  documents.value.filter((doc) => doc.state === "archived"),
);
const selected = computed(
  () => documents.value.find((doc) => doc.id === selectedId.value) || null,
);
const visible = computed(() => {
  const base = view.value === "archive" ? archive.value : inbox.value;
  const query = search.value.trim().toLowerCase();
  return query
    ? base.filter((doc) =>
        [doc.title, doc.original_name, doc.category, ...doc.tags]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(query),
      )
    : base;
});

function message(text, error = false) {
  notice.value = text;
  isError.value = error;
  if (!error)
    setTimeout(() => {
      if (notice.value === text) notice.value = "";
    }, 5000);
}

async function refresh() {
  const [docData, eventData, statData, health] = await Promise.all([
    request("/documents"),
    request("/events"),
    request("/stats"),
    request("/health"),
  ]);
  documents.value = docData;
  events.value = eventData;
  stats.value = statData;
  groqReady.value = health.groq_configured;
}

onMounted(async () => {
  try {
    await refresh();
  } catch (error) {
    message(error.message, true);
  }
});

function navigate(next) {
  view.value = next;
  search.value = "";
  if (next === "inbox" && selected.value?.state === "archived")
    selectedId.value = null;
  if (next === "archive" && selected.value?.state !== "archived")
    selectedId.value = null;
}

async function uploadFiles(files) {
  if (busy.value) return;
  busy.value = true;
  let added = 0;
  const failures = [];
  for (const [index, file] of files.entries()) {
    progress.value = `Importing ${index + 1} of ${files.length}: ${file.name}`;
    const form = new FormData();
    form.append("file", file);
    try {
      const result = await request("/documents", {
        method: "POST",
        body: form,
      });
      if (!selectedId.value || added === 0) selectedId.value = result.id;
      added += 1;
    } catch (error) {
      failures.push(`${file.name}: ${error.message}`);
    }
  }
  busy.value = false;
  progress.value = "";
  navigate("inbox");
  try {
    await refresh();
  } catch (error) {
    failures.push(error.message);
  }
  message(
    failures.length
      ? `${added} imported. ${failures.join(" ")}`
      : `${added} file${added === 1 ? "" : "s"} staged. Nothing has moved.`,
    failures.length > 0,
  );
}

async function runAction(path, success, options = {}) {
  busy.value = true;
  progress.value = options.label || "";
  try {
    const result = await request(path, {
      method: options.method || "POST",
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    await refresh();
    message(success);
    return result;
  } catch (error) {
    message(error.message, true);
    return null;
  } finally {
    busy.value = false;
    progress.value = "";
  }
}

function analyze(doc) {
  return runAction(
    `/documents/${doc.id}/analyze`,
    "Proposal ready. Read the quote and approve it before filing.",
    { label: `Reading ${doc.original_name}…` },
  );
}
function saveProposal(doc, body) {
  return runAction(
    `/documents/${doc.id}/proposal`,
    "Your correction is saved. Review it again before approval.",
    { method: "PUT", body },
  );
}
function approve(doc) {
  return runAction(
    `/documents/${doc.id}/approve`,
    "Approved. This file can now be moved to the archive.",
  );
}
async function fileDocument(doc) {
  const result = await runAction(
    `/documents/${doc.id}/archive`,
    "Filed safely. You can undo this move.",
  );
  if (result) navigate("archive");
}
async function undo(doc) {
  const result = await runAction(
    `/documents/${doc.id}/undo`,
    "Move undone. The file is back in your inbox for review.",
  );
  if (result) navigate("inbox");
}

async function analyzeAll() {
  const pending = inbox.value.filter((doc) => doc.state === "inbox");
  if (!pending.length || busy.value) return;
  busy.value = true;
  let completed = 0;
  const failures = [];
  for (const [index, doc] of pending.entries()) {
    progress.value = `Reading ${index + 1} of ${pending.length}: ${doc.original_name}`;
    try {
      await request(`/documents/${doc.id}/analyze`, { method: "POST" });
      completed += 1;
    } catch (error) {
      failures.push(`${doc.original_name}: ${error.message}`);
    }
  }
  busy.value = false;
  progress.value = "";
  await refresh();
  message(
    failures.length
      ? `${completed} analyzed. ${failures.join(" ")}`
      : `${completed} proposals ready for review.`,
    failures.length > 0,
  );
}

async function archiveApproved() {
  const approved = inbox.value.filter(
    (doc) => doc.state === "ready" && doc.reviewed_at,
  );
  if (!approved.length || busy.value) return;
  if (
    !confirm(
      `Move ${approved.length} approved file${approved.length === 1 ? "" : "s"} into the archive? Every move can be undone.`,
    )
  )
    return;
  busy.value = true;
  let completed = 0;
  const failures = [];
  for (const [index, doc] of approved.entries()) {
    progress.value = `Filing ${index + 1} of ${approved.length}: ${doc.title}`;
    try {
      await request(`/documents/${doc.id}/archive`, { method: "POST" });
      completed += 1;
    } catch (error) {
      failures.push(`${doc.original_name}: ${error.message}`);
    }
  }
  busy.value = false;
  progress.value = "";
  await refresh();
  message(
    failures.length
      ? `${completed} filed. ${failures.join(" ")}`
      : `${completed} file${completed === 1 ? "" : "s"} safely filed.`,
    failures.length > 0,
  );
}

function eventLabel(action) {
  return (
    {
      uploaded: "Imported",
      analyzed: "AI proposal created",
      edited: "Proposal corrected",
      approved: "Reviewed and approved",
      archived: "Moved to archive",
      undone: "Move undone",
    }[action] || action
  );
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <button class="brand" @click="navigate('overview')">
        <span class="brand-mark">s<span>.</span></span
        ><span>stillroom</span>
      </button>
      <span class="side-label">WORKSPACE</span>
      <nav aria-label="Main navigation">
        <button
          :class="{ active: view === 'overview' }"
          @click="navigate('overview')"
        >
          <span>◫</span> Overview</button
        ><button
          :class="{ active: view === 'inbox' }"
          @click="navigate('inbox')"
        >
          <span>▤</span> Inbox <i>{{ inbox.length }}</i></button
        ><button
          :class="{ active: view === 'archive' }"
          @click="navigate('archive')"
        >
          <span>▧</span> Archive <i>{{ archive.length }}</i></button
        ><button
          :class="{ active: view === 'activity' }"
          @click="navigate('activity')"
        >
          <span>⌁</span> Activity
        </button>
      </nav>
      <div class="side-spacer"></div>
      <div class="side-note">
        <span>✳</span><strong>One less pile<br />to think about.</strong>
        <p>Import. Review. File. Undo whenever you need to.</p>
      </div>
      <div class="connection">
        <span :class="{ ready: groqReady }"></span>
        <div>
          <strong>{{ groqReady ? "AI ready" : "Groq key needed" }}</strong
          ><small>{{
            groqReady ? "Open-weight GPT OSS 120B" : "Set GROQ_API_KEY in .env"
          }}</small>
        </div>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="breadcrumb">
          WORKSPACE <span>/</span>
          {{
            view === "overview"
              ? "Overview"
              : view === "inbox"
                ? "Inbox"
                : view === "archive"
                  ? "Archive"
                  : "Activity"
          }}
        </div>
        <div class="top-right">
          <span>LOCAL WORKSPACE</span><span class="avatar">sr.</span>
        </div>
      </header>
      <div
        v-if="notice"
        class="notice"
        :class="{ error: isError }"
        role="status"
      >
        {{ notice }}<button @click="notice = ''" aria-label="Dismiss">×</button>
      </div>
      <div v-if="busy && progress" class="progress-banner">
        <span class="pulse"></span>{{ progress }}
      </div>

      <div v-if="view === 'overview'" class="content">
        <div class="eyebrow">
          <span class="dot"></span> THE QUIET WAY THROUGH
        </div>
        <div class="hero">
          <div>
            <h1>Let the paperwork<br /><em>settle.</em></h1>
            <p>
              Stillroom reads the pile, proposes a place for each file, and
              waits for your approval. Every move leaves a trail back.
            </p>
          </div>
          <span class="hero-sun">✺</span>
        </div>
        <div class="stats">
          <div>
            <span>IN THE INBOX</span
            ><strong>{{ String(stats.inbox).padStart(2, "0") }}</strong
            ><small>Waiting to be read</small>
          </div>
          <div>
            <span>READY FOR REVIEW</span
            ><strong>{{ String(stats.ready).padStart(2, "0") }}</strong
            ><small>{{ stats.approved }} approved to file</small>
          </div>
          <div>
            <span>SAFELY FILED</span
            ><strong>{{ String(stats.archived).padStart(2, "0") }}</strong
            ><small>Every move is reversible</small>
          </div>
        </div>
        <div class="overview-grid">
          <section>
            <div class="section-head">
              <div>
                <span class="eyebrow">START HERE</span>
                <h2>Make a little space.</h2>
              </div>
            </div>
            <UploadPanel :busy="busy" @files="uploadFiles" />
          </section>
          <section class="workflow">
            <span class="eyebrow">HOW IT WORKS</span>
            <h2>Three small steps.</h2>
            <div>
              <span>01</span>
              <p>
                <strong>Drop in the clutter</strong
                ><small
                  >Text files and PDFs are copied into a private staging
                  area.</small
                >
              </p>
            </div>
            <div>
              <span>02</span>
              <p>
                <strong>Review the proposal</strong
                ><small
                  >An open-weight model suggests a title and home, with a quote
                  from the file.</small
                >
              </p>
            </div>
            <div>
              <span>03</span>
              <p>
                <strong>File with an undo button</strong
                ><small
                  >Nothing moves until you approve it. Collisions never
                  overwrite files.</small
                >
              </p>
            </div>
          </section>
        </div>
        <section class="recent">
          <div class="section-head">
            <div>
              <span class="eyebrow">IN MOTION</span>
              <h2>Recent files</h2>
            </div>
            <button class="text-link" @click="navigate('inbox')">
              Open inbox ↗
            </button>
          </div>
          <div v-if="documents.length" class="recent-list">
            <DocumentRow
              v-for="doc in documents.slice(0, 4)"
              :key="doc.id"
              :document="doc"
              @select="
                (item) => {
                  selectedId = item.id;
                  navigate(item.state === 'archived' ? 'archive' : 'inbox');
                }
              "
            />
          </div>
          <div v-else class="empty-inline">
            The room is quiet. Drop a file above to begin.
          </div>
        </section>
      </div>

      <div v-else-if="view === 'inbox' || view === 'archive'" class="content">
        <div class="page-head">
          <div>
            <span class="eyebrow">{{
              view === "inbox" ? "THE INTAKE" : "WHERE THINGS BELONG"
            }}</span>
            <h1>
              {{ view === "inbox" ? "Your inbox" : "The archive"
              }}<span class="title-dot">.</span>
            </h1>
            <p>
              {{
                view === "inbox"
                  ? "Analyze the pile, check every suggestion, and approve the good ones."
                  : "A searchable home for the files you chose to keep. Every move can be undone."
              }}
            </p>
          </div>
          <div class="head-actions">
            <a
              v-if="view === 'archive'"
              class="button secondary"
              href="/api/manifest.csv"
              >↓ Export manifest</a
            ><button
              v-if="view === 'inbox' && stats.inbox && groqReady"
              class="button secondary"
              :disabled="busy"
              @click="analyzeAll"
            >
              ✳ Analyze {{ stats.inbox }}</button
            ><button
              v-if="view === 'inbox' && stats.approved"
              class="button primary"
              :disabled="busy"
              @click="archiveApproved"
            >
              File {{ stats.approved }} approved →
            </button>
          </div>
        </div>
        <div v-if="view === 'inbox'" class="compact-upload">
          <UploadPanel :busy="busy" @files="uploadFiles" />
        </div>
        <div class="workspace-grid">
          <section class="file-list">
            <div class="list-toolbar">
              <span
                >{{ visible.length }} FILE{{
                  visible.length === 1 ? "" : "S"
                }}</span
              ><input
                v-model="search"
                type="search"
                placeholder="Search name, category, tag…"
                aria-label="Search files"
              />
            </div>
            <DocumentRow
              v-for="doc in visible"
              :key="doc.id"
              :document="doc"
              :selected="selectedId === doc.id"
              @select="(item) => (selectedId = item.id)"
            />
            <div v-if="!visible.length" class="empty-list">
              <span>⌁</span
              ><strong>{{
                search
                  ? "No matching files."
                  : view === "archive"
                    ? "Nothing filed yet."
                    : "Your inbox is clear."
              }}</strong>
              <p>
                {{
                  search
                    ? "Try a different search."
                    : view === "archive"
                      ? "Approved files will appear here after you file them."
                      : "Drop a file above to get started."
                }}
              </p>
            </div>
          </section>
          <DocumentDetail
            v-if="
              selected &&
              (view === 'archive'
                ? selected.state === 'archived'
                : selected.state !== 'archived')
            "
            :document="selected"
            :busy="busy"
            :groq-ready="groqReady"
            @analyze="analyze"
            @save="saveProposal"
            @approve="approve"
            @archive="fileDocument"
            @undo="undo"
          />
          <div v-else class="select-prompt">
            <span>↖</span>
            <p>
              Select a file to inspect its source, AI proposal, and move
              history.
            </p>
          </div>
        </div>
      </div>

      <div v-else class="content">
        <div class="page-head">
          <div>
            <span class="eyebrow">EVERY STEP LEAVES A TRACE</span>
            <h1>Activity<span class="title-dot">.</span></h1>
            <p>
              Uploads, AI proposals, approvals, moves, and reversals are
              recorded here.
            </p>
          </div>
        </div>
        <div class="activity-list">
          <div v-for="event in events" :key="event.id" class="activity-row">
            <span class="activity-icon">{{
              event.action === "archived"
                ? "↗"
                : event.action === "undone"
                  ? "↶"
                  : "✳"
            }}</span>
            <div>
              <strong>{{ eventLabel(event.action) }}</strong
              ><small>{{
                event.path ||
                documents.find((doc) => doc.id === event.document_id)
                  ?.original_name ||
                event.document_id
              }}</small>
            </div>
            <time>{{
              displayDate(event.at, { dateStyle: "medium", timeStyle: "short" })
            }}</time>
          </div>
          <div v-if="!events.length" class="empty-inline">
            Your activity trail starts with the first upload.
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
