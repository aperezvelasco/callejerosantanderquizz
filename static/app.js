// Global Game State
const state = {
    username: localStorage.getItem('santander_quiz_username') || null,
    isRegistered: localStorage.getItem('santander_quiz_registered') === 'true',
    guestId: localStorage.getItem('santander_quiz_guest_id') || null,
    theme: localStorage.getItem('santander_quiz_theme') || 'dark-theme',

    // Map Game State
    map: null,
    boundaryLayer: null,
    guessMarker: null,
    streetLayer: null,
    projectionLine: null,
    targetStreet: null,
    gameActive: false,
    guessesRemaining: 10,

    // Map Stats
    points: parseInt(localStorage.getItem('map_game_points')) || 0,
    rounds: parseInt(localStorage.getItem('map_game_rounds')) || 0,
    hits: parseInt(localStorage.getItem('map_game_hits')) || 0,

    // Quiz State
    questions: [],
    currentQuestionIdx: 0,
    quizCorrectAnswersCount: 0
};

// DOM Elements
const els = {
    themeToggle: document.getElementById('theme-toggle'),
    navButtons: document.querySelectorAll('.nav-btn'),
    tabPanels: document.querySelectorAll('.tab-panel'),
    usernameDisplay: document.getElementById('display-username'),
    userBadgeContainer: document.getElementById('user-badge-container'),
    authPanel: document.getElementById('auth-panel'),

    // Auth Forms and Tab Buttons
    tabLoginBtn: document.getElementById('tab-login-btn'),
    tabRegisterBtn: document.getElementById('tab-register-btn'),
    loginForm: document.getElementById('login-form'),
    registerForm: document.getElementById('register-form'),
    loginEmail: document.getElementById('login-email'),
    loginPassword: document.getElementById('login-password'),
    registerEmail: document.getElementById('register-email'),
    registerConfirmEmail: document.getElementById('register-confirm-email'),
    registerPassword: document.getElementById('register-password'),
    btnLogout: document.getElementById('btn-logout'),

    // Map Game Elements
    targetStreetDisplay: document.getElementById('target-street-display'),
    gamePoints: document.getElementById('game-points'),
    gameRounds: document.getElementById('game-rounds'),
    gameHits: document.getElementById('game-hits'),
    resultPanel: document.getElementById('result-panel'),
    resultTitle: document.getElementById('result-title'),
    resultStatusBadge: document.getElementById('result-status-badge'),
    resultDistance: document.getElementById('result-distance'),
    resultScore: document.getElementById('result-score'),
    resultCommentary: document.getElementById('result-commentary'),
    btnNextStreet: document.getElementById('btn-next-street'),
    mapLimitStatusDisplay: document.getElementById('map-limit-status-display'),
    mapGuessesRemaining: document.getElementById('map-guesses-remaining'),

    // Quiz Elements
    quizQuestionsContainer: document.getElementById('quiz-questions-container'),
    quizProgress: document.getElementById('quiz-progress'),
    quizSummary: document.getElementById('quiz-summary'),
    quizSummaryText: document.getElementById('quiz-summary-text'),
    quizScoreVal: document.getElementById('quiz-score-val'),
    btnGoToLeaderboard: document.getElementById('btn-go-to-leaderboard'),

    // Leaderboard
    leaderboardLockedCard: document.getElementById('leaderboard-locked-card'),
    leaderboardCard: document.getElementById('leaderboard-card'),
    leaderboardBody: document.getElementById('leaderboard-body'),
    btnShowLogin: document.getElementById('btn-show-login')
};

// Map configuration
const MAP_CENTER = [43.462778, -3.805]; // Santander coordinates
const ZOOM_LEVEL = 13;
const TILE_URLS = {
    'dark-theme': 'https://{s}.basemaps.cartocdn.com/rastertiles/dark_nolabels/{z}/{x}/{y}.png',
    'light-theme': 'https://{s}.basemaps.cartocdn.com/rastertiles/light_nolabels/{z}/{x}/{y}.png'
};
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>';

// Initialize the Application
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initTabs();
    initUser();
    initMap();
    initAuthTabs();

    // Setup event listeners
    els.themeToggle.addEventListener('click', toggleTheme);
    els.btnNextStreet.addEventListener('click', () => {
        if (state.guessesRemaining <= 0) {
            syncDailyStats();
        } else {
            loadNewTargetStreet();
        }
    });
    els.loginForm.addEventListener('submit', handleLoginSubmit);
    els.registerForm.addEventListener('submit', handleRegisterSubmit);
    els.btnLogout.addEventListener('click', handleLogout);

    if (els.btnGoToLeaderboard) {
        els.btnGoToLeaderboard.addEventListener('click', () => {
            syncDailyStats();
        });
    }
});

// Theme Management
function initTheme() {
    document.body.className = state.theme;
}

function toggleTheme() {
    state.theme = state.theme === 'dark-theme' ? 'light-theme' : 'dark-theme';
    document.body.className = state.theme;
    localStorage.setItem('santander_quiz_theme', state.theme);

    // Update map tiles if map initialized
    if (state.map) {
        state.tileLayer.setUrl(TILE_URLS[state.theme]);
        // Update boundary layer style according to theme
        if (state.boundaryLayer) {
            state.boundaryLayer.setStyle(getBoundaryStyle());
        }
    }
}

// Tab navigation handler
function initTabs() {
    els.navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            if (btn.disabled) return;
            const targetTab = btn.getAttribute('data-tab');
            switchTab(targetTab);
        });
    });
}

function switchTab(tabId) {
    els.tabPanels.forEach(panel => {
        if (panel.id === tabId) {
            panel.classList.add('active');
        } else {
            panel.classList.remove('active');
        }
    });

    // Update active state in nav buttons
    els.navButtons.forEach(btn => {
        if (btn.getAttribute('data-tab') === tabId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    if (tabId === 'map-game-tab') {
        setTimeout(() => {
            if (state.map) {
                state.map.invalidateSize();
                state.map.setView(MAP_CENTER, ZOOM_LEVEL);
            }
        }, 100);
    }
}

// User Profile management
function initUser() {
    if (!state.guestId) {
        state.guestId = 'guest_' + Math.random().toString(36).substring(2, 11);
        localStorage.setItem('santander_quiz_guest_id', state.guestId);
    }

    if (state.username && state.isRegistered) {
        els.usernameDisplay.textContent = state.username;
        if (els.userBadgeContainer) {
            els.userBadgeContainer.classList.remove('hidden');
        }
        els.btnLogout.classList.remove('hidden');
        document.querySelector('.header-actions').classList.remove('hidden');
    } else {
        els.usernameDisplay.textContent = '';
        if (els.userBadgeContainer) {
            els.userBadgeContainer.classList.add('hidden');
        }
        els.btnLogout.classList.add('hidden');

        // Show navigation bar, but disable all buttons except 'Inicio'
        const nav = document.querySelector('.app-nav');
        if (nav) {
            nav.style.display = 'flex';
        }
        els.navButtons.forEach(btn => {
            const tab = btn.getAttribute('data-tab');
            if (tab === 'welcome-tab') {
                btn.disabled = false;
                btn.classList.add('active');
            } else {
                btn.disabled = true;
                btn.classList.remove('active');
            }
        });
        switchTab('welcome-tab');
        return;
    }

    // Load stats display
    els.gamePoints.textContent = state.points;
    els.gameRounds.textContent = state.rounds;
    els.gameHits.textContent = state.hits;

    // Load remaining limit statistics and progression
    syncDailyStats();
}

function syncDailyStats() {
    const userToQuery = (state.username && state.isRegistered) ? state.username : state.guestId;
    if (!userToQuery) return;

    fetch(`/quiz/user-stats?username=${encodeURIComponent(userToQuery)}`)
        .then(res => {
            if (!res.ok) throw new Error("Could not fetch user stats");
            return res.json();
        })
        .then(data => {
            state.guessesRemaining = data.map_guesses_limit - data.map_guesses_today;
            els.mapGuessesRemaining.textContent = `${state.guessesRemaining} / 10`;

            const quizAnswered = data.quiz_questions_answered_today;
            const quizTotal = data.quiz_questions_total_today;

            if (data.is_registered) {
                state.points = data.total_points;
                localStorage.setItem('map_game_points', state.points);
                els.gamePoints.textContent = state.points;
            }

            // Progression State Machine
            const nav = document.querySelector('.app-nav');
            nav.style.display = 'flex'; // Show navigation bar

            // Disable all nav buttons by default
            els.navButtons.forEach(btn => {
                btn.disabled = true;
                btn.classList.remove('active');
            });

            if (state.guessesRemaining > 0) {
                // Phase 1: Map Game
                const mapBtn = document.querySelector('.nav-btn[data-tab="map-game-tab"]');
                mapBtn.disabled = false;
                mapBtn.classList.add('active');
                switchTab('map-game-tab');
            } else if (quizAnswered < quizTotal) {
                // Phase 2: Daily Quiz
                const quizBtn = document.querySelector('.nav-btn[data-tab="quiz-tab"]');
                quizBtn.disabled = false;
                quizBtn.classList.add('active');
                switchTab('quiz-tab');
                startDailyQuiz();
            } else {
                // Phase 3: Leaderboard Only
                const leadBtn = document.querySelector('.nav-btn[data-tab="leaderboard-tab"]');
                leadBtn.disabled = false;
                leadBtn.classList.add('active');
                switchTab('leaderboard-tab');
                loadLeaderboard();
            }
        })
        .catch(err => console.error("Error syncing daily stats:", err));
}

function initAuthTabs() {
    els.tabLoginBtn.addEventListener('click', () => {
        els.tabLoginBtn.classList.add('active');
        els.tabRegisterBtn.classList.remove('active');
        els.loginForm.classList.remove('hidden');
        els.registerForm.classList.add('hidden');
    });

    els.tabRegisterBtn.addEventListener('click', () => {
        els.tabRegisterBtn.classList.add('active');
        els.tabLoginBtn.classList.remove('active');
        els.registerForm.classList.remove('hidden');
        els.loginForm.classList.add('hidden');
    });
}

function handleLoginSubmit(e) {
    e.preventDefault();
    const email = els.loginEmail.value.trim();
    const password = els.loginPassword.value;
    if (!email || !password) return;

    fetch('/users/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => { throw new Error(err.detail || 'Error al iniciar sesión'); });
        }
        return res.json();
    })
    .then(user => {
        state.username = user.username;
        state.isRegistered = true;
        localStorage.setItem('santander_quiz_username', user.username);
        localStorage.setItem('santander_quiz_registered', 'true');

        state.rounds = 0;
        state.hits = 0;
        localStorage.removeItem('map_game_rounds');
        localStorage.removeItem('map_game_hits');

        initUser();
    })
    .catch(err => {
        alert(err.message);
    });
}

function handleRegisterSubmit(e) {
    e.preventDefault();
    const email = els.registerEmail.value.trim();
    const confirm_email = els.registerConfirmEmail.value.trim();
    const password = els.registerPassword.value;

    if (!email || !confirm_email || !password) return;

    if (email !== confirm_email) {
        alert("Los correos electrónicos no coinciden.");
        return;
    }

    fetch('/users/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, confirm_email, password })
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => { throw new Error(err.detail || 'Error al registrarse'); });
        }
        return res.json();
    })
    .then(() => {
        return fetch('/users/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => { throw new Error(err.detail || 'Error al iniciar sesión tras registro'); });
        }
        return res.json();
    })
    .then(user => {
        state.username = user.username;
        state.isRegistered = true;
        localStorage.setItem('santander_quiz_username', user.username);
        localStorage.setItem('santander_quiz_registered', 'true');

        state.rounds = 0;
        state.hits = 0;
        localStorage.removeItem('map_game_rounds');
        localStorage.removeItem('map_game_hits');

        initUser();
    })
    .catch(err => {
        alert(err.message);
    });
}

function handleLogout() {
    state.username = null;
    state.isRegistered = false;
    localStorage.removeItem('santander_quiz_username');
    localStorage.removeItem('santander_quiz_registered');

    state.points = 0;
    state.rounds = 0;
    state.hits = 0;
    localStorage.removeItem('map_game_points');
    localStorage.removeItem('map_game_rounds');
    localStorage.removeItem('map_game_hits');

    initUser();
}

// Leaflet Map Game Implementation
function initMap() {
    state.map = L.map('blind-map', {
        zoomControl: true,
        maxZoom: 18,
        minZoom: 12
    }).setView(MAP_CENTER, ZOOM_LEVEL);

    state.tileLayer = L.tileLayer(TILE_URLS[state.theme], {
        attribution: ATTRIBUTION
    }).addTo(state.map);

    fetch('/quiz/boundary')
        .then(res => {
            if (!res.ok) throw new Error("Boundary endpoint not available");
            return res.json();
        })
        .then(boundaryGeojson => {
            state.boundaryLayer = L.geoJSON(boundaryGeojson, {
                style: getBoundaryStyle()
            }).addTo(state.map);
        })
        .catch(err => {
            console.log("Boundary loading note: falls back to default layout", err);
        });

    state.map.on('click', handleMapClick);
    loadNewTargetStreet();
}

function getBoundaryStyle() {
    const isDark = state.theme === 'dark-theme';
    return {
        color: isDark ? '#6c5ce7' : '#5f27cd',
        weight: 2,
        fillColor: isDark ? '#6c5ce7' : '#5f27cd',
        fillOpacity: 0.02,
        dashArray: '6, 6',
        interactive: false
    };
}

function loadNewTargetStreet() {
    if (state.guessesRemaining <= 0) {
        state.gameActive = false;
        els.targetStreetDisplay.innerHTML = `<span style="color: var(--danger)">Límite de mapa alcanzado hoy (10/10)</span>`;
        return;
    }

    if (state.guessMarker) state.map.removeLayer(state.guessMarker);
    if (state.streetLayer) state.map.removeLayer(state.streetLayer);
    if (state.projectionLine) state.map.removeLayer(state.projectionLine);

    state.guessMarker = null;
    state.streetLayer = null;
    state.projectionLine = null;

    els.resultPanel.classList.add('hidden');
    els.targetStreetDisplay.textContent = "Buscando calle...";
    state.gameActive = false;

    state.map.setView(MAP_CENTER, ZOOM_LEVEL);

    fetch('/quiz/random-street')
        .then(res => {
            if (!res.ok) throw new Error("Unable to fetch random street");
            return res.json();
        })
        .then(data => {
            state.targetStreet = data.name;
            els.targetStreetDisplay.textContent = data.name;
            state.gameActive = true;
        })
        .catch(err => {
            console.error("Error fetching random street:", err);
            els.targetStreetDisplay.textContent = "Error al cargar calle";
        });
}

function handleMapClick(e) {
    if (!state.gameActive) return;
    if (state.guessesRemaining <= 0) return;

    state.gameActive = false;
    const clickLatLng = e.latlng;

    state.guessMarker = L.marker(clickLatLng, {
        icon: L.divIcon({
            className: 'guess-pin-icon',
            html: '📍',
            iconSize: [30, 30],
            iconAnchor: [15, 26]
        })
    }).addTo(state.map);

    fetch('/quiz/guess-street', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            street_name: state.targetStreet,
            lat: clickLatLng.lat,
            lng: clickLatLng.lng,
            username: (state.username && state.isRegistered) ? state.username : state.guestId
        })
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => { throw new Error(err.detail || 'Fallo en validación'); });
        }
        return res.json();
    })
    .then(result => {
        displayGuessResult(clickLatLng, result);
    })
    .catch(err => {
        console.error("Error submitting guess:", err);
        state.gameActive = true;
        if (state.guessMarker) state.map.removeLayer(state.guessMarker);
        alert(err.message);
    });
}

function displayGuessResult(clickLatLng, result) {
    const distance = result.distance_meters;
    const closestLatLng = L.latLng(result.closest_point.lat, result.closest_point.lng);
    const isCorrect = result.is_correct;

    const roundScore = isCorrect ? 30 : 0;

    state.rounds += 1;
    state.points += roundScore;
    if (isCorrect) state.hits += 1;

    localStorage.setItem('map_game_rounds', state.rounds);
    localStorage.setItem('map_game_points', state.points);
    localStorage.setItem('map_game_hits', state.hits);

    els.gamePoints.textContent = state.points;
    els.gameRounds.textContent = state.rounds;
    els.gameHits.textContent = state.hits;

    if (result.hasOwnProperty('guesses_remaining')) {
        state.guessesRemaining = result.guesses_remaining;
        els.mapGuessesRemaining.textContent = `${state.guessesRemaining} / 10`;
    }

    const streetStyle = {
        color: isCorrect ? '#00b894' : '#00cec9',
        weight: 6,
        opacity: 0.8,
        lineJoin: 'round',
        lineCap: 'round'
    };

    state.streetLayer = L.geoJSON(result.street_geometry, {
        style: streetStyle
    }).addTo(state.map);

    state.projectionLine = L.polyline([clickLatLng, closestLatLng], {
        color: '#d63031',
        weight: 3,
        dashArray: '5, 8',
        opacity: 0.9
    }).addTo(state.map);

    const bounds = L.latLngBounds([clickLatLng, closestLatLng]);
    state.map.fitBounds(bounds, { padding: [60, 60] });

    els.resultPanel.classList.remove('hidden');
    els.resultCard = document.getElementById('result-panel');

    if (isCorrect) {
        els.resultCard.className = "panel-card result-card success-result";
        els.resultTitle.textContent = "¡Acertaste! 🎉";
        els.resultStatusBadge.textContent = "Correcto";
        els.resultCommentary.textContent = "Excelente geolocalización, estás dentro del margen reglamentario.";
    } else {
        els.resultCard.className = "panel-card result-card fail-result";
        els.resultTitle.textContent = "¡Casi! 🗺️";
        els.resultStatusBadge.textContent = "Fuera de rango";

        if (distance < 100) {
            els.resultCommentary.textContent = "Muy cerca, te has desviado por pocos metros.";
        } else if (distance < 500) {
            els.resultCommentary.textContent = "Conoces el barrio, pero marcaste un poco apartado.";
        } else {
            els.resultCommentary.textContent = "Esa calle está ubicada en otra zona del municipio.";
        }
    }

    els.resultDistance.textContent = `${distance.toLocaleString()} metros`;
    els.resultScore.textContent = `+${roundScore} pts`;

    if (state.guessesRemaining <= 0) {
        state.gameActive = false;
        els.targetStreetDisplay.innerHTML = `<span style="color: var(--danger)">Límite de mapa alcanzado hoy (10/10)</span>`;
        els.btnNextStreet.textContent = "Comenzar Quiz Diario ➔";
    } else {
        els.btnNextStreet.textContent = "Siguiente Calle ➔";
    }
}

// Daily Quiz tab controller
function startDailyQuiz() {
    els.quizSummary.classList.add('hidden');
    els.quizQuestionsContainer.innerHTML = '<div class="loading-state"><p>Cargando preguntas de hoy...</p></div>';

    state.questions = [];
    state.currentQuestionIdx = 0;
    state.quizCorrectAnswersCount = 0;

    const userToQuery = (state.username && state.isRegistered) ? state.username : state.guestId;

    fetch(`/quiz/daily?username=${encodeURIComponent(userToQuery)}`)
        .then(res => {
            if (!res.ok) throw new Error("Error loading daily questions");
            return res.json();
        })
        .then(data => {
            state.questions = data;
            if (state.questions.length === 0) {
                els.quizQuestionsContainer.innerHTML = '<div class="loading-state"><p>No hay preguntas disponibles hoy.</p></div>';
            } else {
                let unansweredIdx = -1;
                let correctCount = 0;
                state.questions.forEach((q, idx) => {
                    if (q.answered) {
                        if (q.was_correct) {
                            correctCount++;
                        }
                    } else if (unansweredIdx === -1) {
                        unansweredIdx = idx;
                    }
                });

                state.quizCorrectAnswersCount = correctCount;
                if (unansweredIdx === -1) {
                    state.currentQuestionIdx = state.questions.length;
                } else {
                    state.currentQuestionIdx = unansweredIdx;
                }

                renderQuizQuestion();
            }
        })
        .catch(err => {
            console.error("Error loading quiz:", err);
            els.quizQuestionsContainer.innerHTML = '<div class="loading-state"><p>Error al cargar el cuestionario diario.</p></div>';
        });
}

function renderQuizQuestion() {
    const qCount = state.questions.length;
    const progressPercent = (state.currentQuestionIdx / qCount) * 100;
    els.quizProgress.style.width = `${progressPercent}%`;

    if (state.currentQuestionIdx >= qCount) {
        displayQuizSummary();
        return;
    }

    const q = state.questions[state.currentQuestionIdx];
    els.quizQuestionsContainer.innerHTML = '';

    const card = document.createElement('div');
    card.className = 'panel-card quiz-question-card';

    const indexLabel = document.createElement('div');
    indexLabel.className = 'question-index';
    indexLabel.textContent = `Pregunta ${state.currentQuestionIdx + 1} de ${qCount}`;
    card.appendChild(indexLabel);

    const promptText = document.createElement('h3');
    promptText.className = 'question-prompt';
    promptText.textContent = q.prompt;
    card.appendChild(promptText);

    if (q.choices && q.choices.length > 0) {
        const choicesDiv = document.createElement('div');
        choicesDiv.className = 'choices-layout';

        q.choices.forEach((choice, idx) => {
            const btn = document.createElement('button');
            btn.className = 'choice-btn';
            btn.dataset.choice = choice;

            const letter = String.fromCharCode(65 + idx); // A, B, C, D
            btn.innerHTML = `<span class="choice-letter">${letter}</span> ${choice}`;

            btn.addEventListener('click', () => submitChoiceAnswer(q.id, choice, btn, choicesDiv));
            choicesDiv.appendChild(btn);
        });
        card.appendChild(choicesDiv);
    } else {
        const openDiv = document.createElement('div');
        openDiv.className = 'open-answer-layout';

        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = 'Separa las calles con comas...';
        input.id = `input-open-q-${q.id}`;
        openDiv.appendChild(input);

        const submitBtn = document.createElement('button');
        submitBtn.className = 'btn btn-primary';
        submitBtn.textContent = 'Enviar respuesta';
        submitBtn.addEventListener('click', () => submitOpenAnswer(q.id, input.value.trim(), openDiv));
        openDiv.appendChild(submitBtn);

        card.appendChild(openDiv);
    }

    els.quizQuestionsContainer.appendChild(card);
}

function submitChoiceAnswer(questionId, selectedChoice, clickedBtn, parentDiv) {
    const buttons = parentDiv.querySelectorAll('.choice-btn');
    buttons.forEach(b => b.disabled = true);

    clickedBtn.classList.add('selected');

    let answerArray = [selectedChoice];
    if (selectedChoice.includes(' -> ')) {
        answerArray = selectedChoice.split(' -> ');
    }

    const userToQuery = (state.username && state.isRegistered) ? state.username : state.guestId;
    const url = `/quiz/${questionId}/answer?username=${encodeURIComponent(userToQuery)}`;

    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer: answerArray })
    })
    .then(res => {
        if (!res.ok) throw new Error("Submission validation error");
        return res.json();
    })
    .then(result => {
        if (result.is_correct) {
            clickedBtn.className = "choice-btn correct-choice";
            state.quizCorrectAnswersCount += 1;
        } else {
            clickedBtn.className = "choice-btn incorrect-choice";

            buttons.forEach(b => {
                const bChoice = b.dataset.choice;
                let matchesCorrect = false;
                if (bChoice.includes(' -> ')) {
                    const bPath = bChoice.split(' -> ');
                    matchesCorrect = JSON.stringify(bPath) === JSON.stringify(result.correct_answer);
                } else {
                    matchesCorrect = result.correct_answer.includes(bChoice);
                }

                if (matchesCorrect) {
                    b.className = "choice-btn correct-choice";
                }
            });
        }

        setTimeout(() => {
            state.currentQuestionIdx += 1;
            renderQuizQuestion();
        }, 2200);
    })
    .catch(err => {
        console.error("Error submitting quiz choice answer:", err);
        buttons.forEach(b => b.disabled = false);
        alert("Ocurrió un error al enviar tu respuesta.");
    });
}

function submitOpenAnswer(questionId, textVal, parentDiv) {
    if (!textVal) return;

    const input = parentDiv.querySelector('input');
    const btn = parentDiv.querySelector('button');
    input.disabled = true;
    btn.disabled = true;

    const answerArray = textVal.split(',').map(s => s.trim()).filter(s => s.length > 0);
    const userToQuery = (state.username && state.isRegistered) ? state.username : state.guestId;
    const url = `/quiz/${questionId}/answer?username=${encodeURIComponent(userToQuery)}`;

    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer: answerArray })
    })
    .then(res => {
        if (!res.ok) throw new Error("Open submission validation error");
        return res.json();
    })
    .then(result => {
        const feedback = document.createElement('div');
        feedback.className = `open-answer-feedback ${result.is_correct ? 'correct' : 'incorrect'}`;

        const correctFormatted = result.correct_answer.join(', ');
        if (result.is_correct) {
            feedback.textContent = "¡Perfecto! Has identificado todas las calles conectadas correctamente.";
            state.quizCorrectAnswersCount += 1;
        } else {
            feedback.innerHTML = `Incorrecto. Te faltaron calles o incluiste algunas erróneas.<br><strong>Respuesta correcta:</strong> ${correctFormatted}`;
        }

        parentDiv.appendChild(feedback);

        setTimeout(() => {
            state.currentQuestionIdx += 1;
            renderQuizQuestion();
        }, 4000);
    })
    .catch(err => {
        console.error("Error submitting open answer:", err);
        input.disabled = false;
        btn.disabled = false;
        alert("Error al validar respuesta abierta.");
    });
}

// Shows final quiz card summary
function displayQuizSummary() {
    els.quizProgress.style.width = '100%';
    els.quizQuestionsContainer.innerHTML = '';
    els.quizSummary.classList.remove('hidden');

    const correctCount = state.quizCorrectAnswersCount;
    const totalCount = state.questions.length;

    els.quizSummaryText.textContent = `Has respondido correctamente a ${correctCount} de ${totalCount} preguntas diarias.`;

    const quizAward = correctCount * 100;
    els.quizScoreVal.textContent = `+${quizAward} pts`;

    if (state.username && state.isRegistered) {
        // Sync stats to lock tabs and reveal classification
        syncDailyStats();
    } else {
        state.points += quizAward;
        localStorage.setItem('map_game_points', state.points);
        els.gamePoints.textContent = state.points;
    }
}

// Leaderboard implementation
function initLeaderboard() {
    loadLeaderboard();
}

function loadLeaderboard() {
    if (!state.username || !state.isRegistered) {
        els.leaderboardLockedCard.classList.remove('hidden');
        els.leaderboardCard.classList.add('hidden');
        return;
    }

    els.leaderboardLockedCard.classList.add('hidden');
    els.leaderboardCard.classList.remove('hidden');
    els.leaderboardBody.innerHTML = '<tr><td colspan="3" class="text-center">Cargando clasificación...</td></tr>';

    fetch(`/quiz/leaderboard?username=${encodeURIComponent(state.username)}`)
        .then(res => {
            if (!res.ok) throw new Error("Leaderboard loading error");
            return res.json();
        })
        .then(data => {
            els.leaderboardBody.innerHTML = '';

            if (data.length === 0) {
                els.leaderboardBody.innerHTML = '<tr><td colspan="3" class="text-center">No hay registros todavía. ¡Sé el primero!</td></tr>';
                return;
            }

            data.forEach((entry, idx) => {
                const tr = document.createElement('tr');

                const tdRank = document.createElement('td');
                const rankNum = idx + 1;
                const rankSpan = document.createElement('span');
                rankSpan.className = `rank-badge rank-${rankNum}`;
                rankSpan.textContent = rankNum;
                tdRank.appendChild(rankSpan);
                tr.appendChild(tdRank);

                const tdUser = document.createElement('td');
                tdUser.textContent = entry.username;
                if (entry.username === state.username) {
                    tdUser.innerHTML = `<strong>${entry.username} (Tú)</strong>`;
                }
                tr.appendChild(tdUser);

                const tdPoints = document.createElement('td');
                tdPoints.textContent = entry.total_points;
                tr.appendChild(tdPoints);

                els.leaderboardBody.appendChild(tr);
            });
        })
        .catch(err => {
            console.error("Error loading leaderboard:", err);
            els.leaderboardBody.innerHTML = '<tr><td colspan="3" class="text-center text-danger">Error al cargar ranking de clasificación.</td></tr>';
        });
}
