/**
 * Geriatric Intake Voice AI - Frontend Application
 *
 * Handles:
 * - WebRTC connection to OpenAI Realtime API
 * - Communication with Python backend for sideband tool handling
 * - Live UI updates from state changes
 */

// State
let peerConnection = null;
let dataChannel = null;
let callId = null;
let stateWebSocket = null;
let isCallActive = false;

// DOM Elements
const statusIndicator = document.getElementById('statusIndicator');
const callButton = document.getElementById('callButton');
const transcript = document.getElementById('transcript');
const actionsSection = document.getElementById('actionsSection');
const downloadButton = document.getElementById('downloadButton');

// Current state data for download
let currentStateData = null;

/**
 * Initialize the application
 */
function init() {
    callButton.addEventListener('click', handleCallButton);
    downloadButton.addEventListener('click', handleDownload);
    updateStatus('ready', 'Ready to start');
}

/**
 * Handle call button click
 */
async function handleCallButton() {
    if (isCallActive) {
        await endCall();
    } else {
        await startCall();
    }
}

/**
 * Update status indicator
 */
function updateStatus(state, text) {
    statusIndicator.className = 'status-indicator ' + state;
    statusIndicator.querySelector('.status-text').textContent = text;
}

/**
 * Start a new call
 */
async function startCall() {
    try {
        updateStatus('connecting', 'Connecting...');
        callButton.disabled = true;

        // Clear previous transcript
        transcript.innerHTML = '<div class="transcript-placeholder">Connecting to voice AI...</div>';
        resetForm();

        // Get ephemeral API key from backend
        // For now, we'll use direct connection - in production, get key from backend
        const apiKey = await getEphemeralKey();

        // Create WebRTC connection
        await createWebRTCConnection(apiKey);

        // Update UI
        isCallActive = true;
        callButton.disabled = false;
        callButton.classList.add('active');
        callButton.querySelector('.button-text').textContent = 'End Call';
        updateStatus('active', 'Call in progress');
        transcript.innerHTML = '';
        actionsSection.style.display = 'none';

    } catch (error) {
        console.error('Failed to start call:', error);
        updateStatus('ready', 'Failed to connect');
        callButton.disabled = false;
        alert('Failed to start call: ' + error.message);
    }
}

/**
 * Get ephemeral API key from backend
 *
 * The backend generates short-lived ephemeral keys from OpenAI.
 * This keeps the main API key secure on the server.
 */
async function getEphemeralKey() {
    const response = await fetch('/api/ephemeral-key');

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || 'Failed to get API key from server');
    }

    const data = await response.json();
    if (!data.key) {
        throw new Error('No API key returned from server');
    }

    return data.key;
}

/**
 * Wait for WebRTC connection to establish
 */
function waitForConnection(pc) {
    return new Promise((resolve, reject) => {
        // Check if already connected
        if (pc.connectionState === 'connected') {
            resolve();
            return;
        }

        const timeout = setTimeout(() => {
            reject(new Error('Connection timeout'));
        }, 10000);

        pc.onconnectionstatechange = () => {
            console.log('Connection state:', pc.connectionState);
            if (pc.connectionState === 'connected') {
                clearTimeout(timeout);
                resolve();
            } else if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
                clearTimeout(timeout);
                reject(new Error('Connection failed'));
            }
        };
    });
}

/**
 * Create WebRTC connection to OpenAI Realtime API
 */
async function createWebRTCConnection(apiKey) {
    // Create peer connection
    peerConnection = new RTCPeerConnection();

    // Set up audio
    const audioEl = document.createElement('audio');
    audioEl.autoplay = true;
    peerConnection.ontrack = (event) => {
        audioEl.srcObject = event.streams[0];
    };

    // Get user microphone
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach(track => {
        peerConnection.addTrack(track, stream);
    });

    // Create data channel for events
    dataChannel = peerConnection.createDataChannel('oai-events');
    dataChannel.onmessage = handleDataChannelMessage;

    // Create offer
    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);

    // Send offer to OpenAI and get answer
    const baseUrl = 'https://api.openai.com/v1/realtime/calls';
    const response = await fetch(baseUrl, {
        method: 'POST',
        body: offer.sdp,
        headers: {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/sdp',
        },
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`OpenAI API error: ${response.status} - ${errorText}`);
    }

    // Get call_id from Location header
    const location = response.headers.get('Location');
    callId = location ? location.split('/').pop() : null;

    if (!callId) {
        throw new Error('No call_id received from OpenAI');
    }

    console.log('Call ID:', callId);

    // Set remote description
    const sdpAnswer = await response.text();
    await peerConnection.setRemoteDescription({
        type: 'answer',
        sdp: sdpAnswer,
    });

    // Wait for ICE connection to establish before starting sideband
    await waitForConnection(peerConnection);

    // Notify backend to start sideband connection
    // Pass the ephemeral key since sideband may need same credentials as WebRTC session
    await notifyBackendStartCall(callId, apiKey);

    // Connect WebSocket for state updates
    connectStateWebSocket(callId);
}

/**
 * Handle messages from WebRTC data channel
 *
 * Note: We don't handle transcripts here - they come from the backend
 * via WebSocket to avoid duplicates. The data channel is just for
 * debugging/monitoring.
 */
function handleDataChannelMessage(event) {
    try {
        const message = JSON.parse(event.data);
        console.log('DataChannel message:', message.type);
        // Transcripts are handled by the backend WebSocket, not here
    } catch (e) {
        console.error('Error parsing data channel message:', e);
    }
}

/**
 * Notify backend to start sideband connection
 */
async function notifyBackendStartCall(callId, ephemeralKey) {
    const response = await fetch('/api/start-call', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ call_id: callId, ephemeral_key: ephemeralKey }),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to start backend connection');
    }

    console.log('Backend sideband connected');
}

/**
 * Connect WebSocket for live state updates
 */
function connectStateWebSocket(callId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/${callId}`;

    stateWebSocket = new WebSocket(wsUrl);

    stateWebSocket.onopen = () => {
        console.log('State WebSocket connected');
    };

    stateWebSocket.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            handleStateMessage(message);
        } catch (e) {
            console.error('Error parsing state message:', e);
        }
    };

    stateWebSocket.onclose = () => {
        console.log('State WebSocket closed');
    };

    stateWebSocket.onerror = (error) => {
        console.error('State WebSocket error:', error);
    };
}

/**
 * Handle state update messages from backend
 */
function handleStateMessage(message) {
    if (message.type === 'transcript') {
        addTranscriptEntry(message.speaker, message.text);
    } else if (message.type === 'state') {
        updateFormFromState(message.data);
        currentStateData = message.data;
    }
}

/**
 * Add entry to transcript
 */
function addTranscriptEntry(speaker, text) {
    if (!text) return;

    const entry = document.createElement('div');
    entry.className = `transcript-entry ${speaker}`;
    entry.innerHTML = `
        <div class="speaker">${speaker === 'assistant' ? 'Assistant' : 'Patient'}</div>
        <div class="text">${escapeHtml(text)}</div>
    `;
    transcript.appendChild(entry);
    transcript.scrollTop = transcript.scrollHeight;
}

/**
 * Update form from state data
 */
function updateFormFromState(data) {
    // Update topic progress
    const topicsCovered = data.meta?.topics_covered || [];
    document.querySelectorAll('.topic').forEach(el => {
        const topic = el.dataset.topic;
        if (topicsCovered.includes(topic)) {
            el.classList.add('covered');
        } else {
            el.classList.remove('covered');
        }
    });

    // Patient info
    updateField('patientName', data.patient?.name);
    updateField('speakerType', formatSpeakerType(data.meta?.speaker_type));

    // Referral
    updateField('referralReason', data.referral_reason);

    // Social history
    const social = data.social_history || {};
    updateField('livingSituation', social.living_situation);
    updateField('supportSystem', social.support_system);
    updateField('activities', social.hobbies_activities);
    updateField('goalsOfCare', social.goals_of_care);

    // ADLs
    const adl = data.functional_status?.adl || {};
    updateAdlGrid('adlGrid', adl, 'adl');
    updateField('adlNotes', adl.notes);

    // IADLs
    const iadl = data.functional_status?.iadl || {};
    updateAdlGrid('iadlGrid', iadl, 'iadl');
    updateField('iadlNotes', iadl.notes);

    // Review of systems
    const ros = data.review_of_systems || {};
    updateField('rosMemory', ros.memory_concerns);
    updateField('rosMood', ros.mood_depression);
    updateField('rosFalls', ros.falls_history);
    updateField('rosSleep', ros.sleep_issues);
    updateField('rosPain', ros.pain);

    // Equipment
    const equipment = data.equipment || {};
    updateField('equipmentGaitAid', equipment.gait_aid);
    updateField('equipmentHearingAids', formatBoolean(equipment.hearing_aids));
    updateField('equipmentGlasses', formatBoolean(equipment.glasses));
    updateField('equipmentGrabBars', formatBoolean(equipment.grab_bars));
    updateField('equipmentShowerChair', formatBoolean(equipment.shower_chair));
    updateField('equipmentRaisedToilet', formatBoolean(equipment.raised_toilet_seat));
    updateField('equipmentHospitalBed', formatBoolean(equipment.hospital_bed));
    updateField('equipmentOxygen', formatBoolean(equipment.oxygen));
    updateField('equipmentOther', equipment.other && equipment.other.length > 0 ? equipment.other.join(', ') : null);

    // Medications
    updateList('medicationsList', data.medications || [], formatMedication);

    // Allergies
    updateList('allergiesList', data.allergies || [], formatAllergy);

    // Medical history
    updateList('medicalHistoryList', data.medical_history || [], formatMedicalHistory);

    // Urgent concerns
    const urgentSection = document.getElementById('urgentSection');
    const urgentList = document.getElementById('urgentList');
    if (data.urgent_concerns && data.urgent_concerns.length > 0) {
        urgentSection.style.display = 'block';
        urgentList.innerHTML = data.urgent_concerns.map(c =>
            `<div class="urgent-item">
                <span class="type">${formatUrgentType(c.concern_type)}:</span>
                ${escapeHtml(c.description)}
            </div>`
        ).join('');
    } else {
        urgentSection.style.display = 'none';
    }
}

/**
 * Update a single field
 */
function updateField(id, value) {
    const el = document.getElementById(id);
    if (el) {
        const newValue = value || '-';
        if (el.textContent !== newValue) {
            el.textContent = newValue;
            el.classList.add('updated');
            setTimeout(() => el.classList.remove('updated'), 1000);
        }
    }
}

/**
 * Update ADL/IADL grid
 */
function updateAdlGrid(gridId, data, prefix) {
    const grid = document.getElementById(gridId);
    if (!grid) return;

    grid.querySelectorAll('.adl-item').forEach(item => {
        const key = item.dataset[prefix];
        const status = data[key] || 'not_assessed';
        const statusEl = item.querySelector('.adl-status');
        if (statusEl) {
            statusEl.textContent = formatAdlStatus(status);
            statusEl.className = 'adl-status ' + status;
        }
    });
}

/**
 * Update a list section
 */
function updateList(containerId, items, formatter) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (items.length === 0) {
        container.innerHTML = '<div class="list-placeholder">None recorded</div>';
    } else {
        container.innerHTML = items.map(formatter).join('');
    }
}

/**
 * Format functions
 */
function formatSpeakerType(type) {
    const types = {
        'patient': 'Patient',
        'caregiver': 'Caregiver',
        'unknown': 'Unknown'
    };
    return types[type] || '-';
}

function formatAdlStatus(status) {
    const statuses = {
        'independent': 'Indep',
        'needs_assistance': 'Assist',
        'dependent': 'Dep',
        'not_assessed': '-'
    };
    return statuses[status] || '-';
}

function formatMedication(med) {
    let details = [];
    if (med.dose) details.push(med.dose);
    if (med.frequency) details.push(med.frequency);
    if (med.purpose) details.push(`for ${med.purpose}`);

    return `<div class="list-item">
        <span class="name">${escapeHtml(med.name)}</span>
        ${details.length ? `<div class="details">${escapeHtml(details.join(' - '))}</div>` : ''}
    </div>`;
}

function formatAllergy(allergy) {
    let details = [];
    if (allergy.reaction) details.push(allergy.reaction);
    if (allergy.severity) details.push(allergy.severity);

    return `<div class="list-item">
        <span class="name">${escapeHtml(allergy.allergen)}</span>
        ${details.length ? `<div class="details">${escapeHtml(details.join(' - '))}</div>` : ''}
    </div>`;
}

function formatMedicalHistory(item) {
    let details = [];
    if (item.year_diagnosed) details.push(item.year_diagnosed);
    if (item.current_status) details.push(item.current_status);

    return `<div class="list-item">
        <span class="name">${escapeHtml(item.condition)}</span>
        ${details.length ? `<div class="details">${escapeHtml(details.join(' - '))}</div>` : ''}
    </div>`;
}

function formatUrgentType(type) {
    const types = {
        'chest_pain': 'Chest Pain',
        'breathing_difficulty': 'Breathing Difficulty',
        'fall_with_injury': 'Fall with Injury',
        'suicidal_ideation': 'Suicidal Ideation',
        'abuse_concern': 'Abuse Concern',
        'acute_confusion': 'Acute Confusion',
        'other_emergency': 'Other Emergency'
    };
    return types[type] || type;
}

function formatBoolean(value) {
    if (value === true) return 'Yes';
    if (value === false) return 'No';
    return null;
}

/**
 * Reset form to initial state
 */
function resetForm() {
    // Reset topic progress
    document.querySelectorAll('.topic').forEach(el => el.classList.remove('covered'));

    // Reset fields
    const fields = [
        'patientName', 'speakerType', 'referralReason',
        'livingSituation', 'supportSystem', 'activities', 'goalsOfCare',
        'adlNotes', 'iadlNotes',
        'rosMemory', 'rosMood', 'rosFalls', 'rosSleep', 'rosPain',
        'equipmentGaitAid', 'equipmentHearingAids', 'equipmentGlasses',
        'equipmentGrabBars', 'equipmentShowerChair', 'equipmentRaisedToilet',
        'equipmentHospitalBed', 'equipmentOxygen', 'equipmentOther'
    ];
    fields.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '-';
    });

    // Reset ADL grids
    document.querySelectorAll('.adl-status').forEach(el => {
        el.textContent = '-';
        el.className = 'adl-status';
    });

    // Reset lists
    document.getElementById('medicationsList').innerHTML =
        '<div class="list-placeholder">No medications recorded</div>';
    document.getElementById('allergiesList').innerHTML =
        '<div class="list-placeholder">No allergies recorded</div>';
    document.getElementById('medicalHistoryList').innerHTML =
        '<div class="list-placeholder">No history recorded</div>';

    // Hide urgent section
    document.getElementById('urgentSection').style.display = 'none';

    currentStateData = null;
}

/**
 * End the current call
 */
async function endCall() {
    updateStatus('ended', 'Call ended');
    isCallActive = false;
    callButton.classList.remove('active');
    callButton.querySelector('.button-text').textContent = 'Start Call';

    // Close WebRTC
    if (peerConnection) {
        peerConnection.close();
        peerConnection = null;
    }

    // Close state WebSocket
    if (stateWebSocket) {
        stateWebSocket.close();
        stateWebSocket = null;
    }

    // Notify backend
    if (callId) {
        try {
            await fetch('/api/end-call', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ call_id: callId }),
            });
        } catch (e) {
            console.error('Error ending call on backend:', e);
        }
        callId = null;
    }

    // Show download button
    if (currentStateData) {
        actionsSection.style.display = 'flex';
    }

    // Reset status after delay
    setTimeout(() => {
        updateStatus('ready', 'Ready to start');
    }, 2000);
}

/**
 * Handle download button
 */
function handleDownload() {
    if (!currentStateData) return;

    const blob = new Blob([JSON.stringify(currentStateData, null, 2)], {
        type: 'application/json'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `intake-${currentStateData.meta?.call_id || 'report'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize on load
document.addEventListener('DOMContentLoaded', init);
