const questions = window.SURVEY_QUESTIONS || [];
const answers = {};
let current = 0;

const sectionTitle = document.getElementById("section-title");
const counter = document.getElementById("counter");
const progressBar = document.getElementById("progress-bar");
const questionText = document.getElementById("question-text");
const likertBlock = document.getElementById("likert-block");
const textBlock = document.getElementById("text-block");
const likertOptions = document.getElementById("likert-options");
const comment = document.getElementById("comment");
const openAnswer = document.getElementById("open-answer");
const errorMessage = document.getElementById("error-message");
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");

function renderLikertOptions(question) {
  likertOptions.innerHTML = "";
  for (let score = 1; score <= 5; score++) {
    const wrapper = document.createElement("div");
    wrapper.className = "likert-option";
    wrapper.innerHTML = `
      <input type="radio" id="score-${score}" name="score" value="${score}">
      <label for="score-${score}">${score}</label>
    `;
    likertOptions.appendChild(wrapper);
  }

  const saved = answers[question.id];
  if (saved?.score) {
    const input = document.querySelector(`input[name="score"][value="${saved.score}"]`);
    if (input) input.checked = true;
  }
  comment.value = saved?.comment || "";
}

function saveCurrent() {
  const question = questions[current];
  if (!question) return;

  if (question.type === "likert") {
    const selected = document.querySelector('input[name="score"]:checked');
    answers[question.id] = {
      question_id: question.id,
      score: selected ? Number(selected.value) : null,
      comment: comment.value.trim()
    };
  } else {
    answers[question.id] = {
      question_id: question.id,
      answer_text: openAnswer.value.trim()
    };
  }
}

function validateCurrent() {
  const question = questions[current];
  errorMessage.textContent = "";

  if (question.type === "likert") {
    const selected = document.querySelector('input[name="score"]:checked');
    if (!selected) {
      errorMessage.textContent = "Veuillez sélectionner une note de 1 à 5.";
      return false;
    }
  }
  return true;
}

function render() {
  const question = questions[current];
  sectionTitle.textContent = question.section;
  counter.textContent = `Question ${current + 1} / ${questions.length}`;
  progressBar.style.width = `${((current + 1) / questions.length) * 100}%`;
  questionText.textContent = question.question;
  errorMessage.textContent = "";

  prevBtn.disabled = current === 0;
  prevBtn.style.opacity = current === 0 ? ".45" : "1";
  nextBtn.textContent = current === questions.length - 1 ? "Envoyer" : "Suivant →";

  if (question.type === "likert") {
    likertBlock.classList.remove("hidden");
    textBlock.classList.add("hidden");
    renderLikertOptions(question);
  } else {
    likertBlock.classList.add("hidden");
    textBlock.classList.remove("hidden");
    openAnswer.value = answers[question.id]?.answer_text || "";
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function submitSurvey() {
  nextBtn.disabled = true;
  nextBtn.textContent = "Envoi...";

  try {
    const response = await fetch("/api/submit", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ answers: Object.values(answers), is_test: Boolean(window.SURVEY_IS_TEST) })
    });

    if (!response.ok) {
      const payload = await response.json();
      throw new Error(payload.detail || "Échec de l’enregistrement.");
    }

    window.location.href = window.SURVEY_IS_TEST ? "/thanks?test=true" : "/thanks";
  } catch (error) {
    errorMessage.textContent = error.message;
    nextBtn.disabled = false;
    nextBtn.textContent = "Envoyer";
  }
}

prevBtn.addEventListener("click", () => {
  saveCurrent();
  if (current > 0) {
    current -= 1;
    render();
  }
});

nextBtn.addEventListener("click", async () => {
  if (!validateCurrent()) return;
  saveCurrent();

  if (current < questions.length - 1) {
    current += 1;
    render();
  } else {
    await submitSurvey();
  }
});

render();
