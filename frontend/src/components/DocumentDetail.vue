<script setup>
import { ref, watch } from "vue";
import { displayDate, size } from "../api";
import StillroomMark from "./StillroomMark.vue";

const props = defineProps({
  document: { type: Object, required: true },
  busy: Boolean,
  groqReady: Boolean,
});
const emit = defineEmits(["analyze", "save", "approve", "archive", "undo"]);
const editing = ref(false);
const draft = ref({});
const categories = [
  "Records",
  "Receipts",
  "Projects",
  "Reading",
  "Personal",
  "Other",
];

watch(
  () => props.document.id,
  () => {
    editing.value = false;
  },
  { immediate: true },
);

function startEdit() {
  draft.value = {
    category: props.document.category,
    title: props.document.title,
    document_date: props.document.document_date || "",
    tags: props.document.tags.join(", "),
  };
  editing.value = true;
}

function save() {
  const documentId = props.document.id;
  emit(
    "save",
    props.document,
    {
      category: draft.value.category,
      title: draft.value.title,
      document_date: draft.value.document_date || null,
      tags: draft.value.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean)
        .slice(0, 5),
    },
    () => {
      if (props.document.id === documentId) editing.value = false;
    },
  );
}
</script>

<template>
  <div class="detail-panel">
    <ol class="review-steps" aria-label="Filing progress">
      <li class="done">1 <span>Imported</span></li>
      <li
        :class="{
          done: document.reviewed_at || document.state === 'archived',
          active: document.state !== 'archived' && !document.reviewed_at,
        }"
      >
        2 <span>Review</span>
      </li>
      <li
        :class="{
          done: document.state === 'archived',
          active: document.state === 'ready' && document.reviewed_at,
        }"
      >
        3 <span>Filed</span>
      </li>
    </ol>
    <div class="detail-top">
      <span class="micro-label">FILE REVIEW</span
      ><a class="download-link" :href="`/api/documents/${document.id}/file`"
        >↓ Original file</a
      >
    </div>
    <div class="detail-file-line">
      <span class="file-icon large" :class="document.extension.slice(1)">{{
        document.extension.slice(1).toUpperCase()
      }}</span>
      <div>
        <h2>{{ document.title || document.original_name }}</h2>
        <p>
          {{ document.original_name }} · {{ size(document.size_bytes) }} · Added
          {{ displayDate(document.created_at) }}
        </p>
      </div>
    </div>

    <template v-if="document.state === 'inbox'"
      ><div class="waiting-card">
        <StillroomMark class="waiting-icon" />
        <h3>Ready for a second pass.</h3>
        <p>
          Stillroom will read this file and propose a name, category, and
          archive location. It won’t move anything yet.
        </p>
        <button
          class="button primary"
          :disabled="busy || !groqReady"
          @click="emit('analyze', document)"
        >
          {{ busy ? "Reading…" : "Analyze with open-weight AI →" }}</button
        ><small v-if="!groqReady">Set GROQ_API_KEY to enable analysis.</small>
      </div></template
    >

    <template v-else
      ><div class="proposal-heading">
        <div>
          <span class="micro-label">PROPOSED HOME</span>
          <h3>{{ document.archived_path || document.suggested_path }}</h3>
        </div>
        <span v-if="document.user_edited" class="edited-badge"
          >EDITED BY YOU</span
        >
      </div>
      <div class="proposal-grid">
        <div>
          <span>CATEGORY</span><strong>{{ document.category }}</strong>
        </div>
        <div>
          <span>DOCUMENT DATE</span
          ><strong>{{ displayDate(document.document_date) }}</strong>
        </div>
        <div>
          <span>TAGS</span
          ><strong>{{
            document.tags.length ? document.tags.join(", ") : "None"
          }}</strong>
        </div>
      </div>
      <div class="summary-card">
        <span class="micro-label">THE SHORT VERSION</span>
        <p>{{ document.summary }}</p>
      </div>
      <div class="evidence-card">
        <span class="micro-label">WHY THIS PROPOSAL?</span>
        <blockquote>“{{ document.evidence_quote }}”</blockquote>
        <small v-if="document.date_quote"
          >Date found in source: “{{ document.date_quote }}”</small
        ><small v-else-if="document.document_date"
          >Date set by you. Check it before filing.</small
        >
      </div>

      <form
        v-if="editing && document.state === 'ready'"
        class="review-form"
        @submit.prevent="save"
      >
        <div class="form-grid">
          <label
            >Category<select v-model="draft.category">
              <option
                v-for="category in categories"
                :key="category"
                :value="category"
              >
                {{ category }}
              </option>
            </select></label
          ><label
            >Document date<input v-model="draft.document_date" type="date"
          /></label>
        </div>
        <label
          >Title<input
            v-model.trim="draft.title"
            required
            minlength="3"
            maxlength="100" /></label
        ><label
          >Tags <small>Comma separated, up to 5</small
          ><input v-model="draft.tags"
        /></label>
        <div class="form-actions">
          <button
            type="button"
            class="button secondary"
            @click="editing = false"
          >
            Cancel</button
          ><button class="button primary" :disabled="busy">
            Save proposal
          </button>
        </div>
      </form>

      <div v-if="document.state === 'ready' && !editing" class="decision-bar">
        <button class="button secondary" :disabled="busy" @click="startEdit">
          Edit proposal</button
        ><button
          v-if="!document.reviewed_at"
          class="button primary"
          :disabled="busy"
          @click="emit('approve', document)"
        >
          Approve suggestion ✓</button
        ><button
          v-else
          class="button dark"
          :disabled="busy"
          @click="emit('archive', document)"
        >
          Move to archive →
        </button>
      </div>
      <div
        v-if="document.state === 'archived'"
        class="decision-bar archived-actions"
      >
        <span
          >Filed {{ displayDate(document.archived_at) }}. The move is recorded
          and reversible.</span
        ><button
          class="button secondary"
          :disabled="busy"
          @click="emit('undo', document)"
        >
          ↶ Undo move
        </button>
      </div>
    </template>

    <div class="source-heading">
      <span class="micro-label">EXTRACTED TEXT</span
      ><small>First 30,000 characters · original available above</small>
    </div>
    <pre class="source-text">{{ document.extracted_text }}</pre>
    <div class="checksum">SHA-256 {{ document.sha256 }}</div>
  </div>
</template>
