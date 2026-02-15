// app.js - DenoiseVision Application
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM fully loaded, initializing app');

  // Load image list if available
  const USE_IMAGE_LIST = typeof AVAILABLE_IMAGES !== 'undefined';
  console.log('USE_IMAGE_LIST:', USE_IMAGE_LIST);

  // App state
  const state = {
    user: null,
    currentScreen: 'login',
    study: null
  };

  // DOM elements
  const screens = {
    login: document.getElementById('login-screen'),
    instructions: document.getElementById('instructions-screen'),
    study: document.getElementById('study-screen'),
    completion: document.getElementById('completion-screen')
  };

  const elements = {
    userInfo: document.getElementById('user-info'),
    userInitials: document.getElementById('user-initials'),
    loginForm: document.getElementById('login-form'),
    initialsInput: document.getElementById('initials'),
    beginStudyBtn: document.getElementById('begin-study-btn'),
    ratingForm: document.getElementById('rating-form'),
    commentsText: document.getElementById('comments'),
    saveProgressBtn: document.getElementById('save-progress-btn'),
    downloadResultsBtn: document.getElementById('download-results-btn'),
    startNewBtn: document.getElementById('start-new-btn'),
    progressFill: document.getElementById('progress-fill'),
    progressText: document.getElementById('progress-text'),
    loadingImages: document.getElementById('loading-images'),
    currentImage: document.getElementById('current-image'),
    totalImages: document.getElementById('total-images'),
    accuracyRate: document.getElementById('accuracy-rate'),
    avgNoisy: document.getElementById('avg-noisy'),
    avgOriginal: document.getElementById('avg-original'),
    avgDenoised: document.getElementById('avg-denoised'),
    currentYear: document.getElementById('current-year')
  };

  // Validate DOM elements
  for (const [key, el] of Object.entries(screens)) {
    if (!el) console.error(`Screen '${key}' not found`);
  }
  for (const [key, el] of Object.entries(elements)) {
    if (!el) console.error(`Element '${key}' not found`);
  }

  // Set current year
  if (elements.currentYear) {
    elements.currentYear.textContent = new Date().getFullYear();
  }

  // Image base paths
  const IMAGE_PATHS = {
    noisy: 'images/noisy/',
    original: 'images/original/',
    denoised: 'images/denoised/'
  };

  // Study configuration
  const STUDY_CONFIG = {
    uniqueImages: 120,
    duplicatePercentage: 15,
    minSpacing: 5
  };

  // Google Apps Script URL
  const GOOGLE_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycby1EeohCe-H6RAf4P9XSqw8_5iJTlPkaZSkOnPVvNRSryzbHmv2bHGUaZnXHsUeTF0XnA/exec';

  // Cache management
  const APP_VERSION = '2.0.1'; // Incremented for this version

  // Initialize the app
  function init() {
    console.log('init: Starting');
    try {
      if (!localStorage.getItem('denoiseVisionVersion') || 
          localStorage.getItem('denoiseVisionVersion') !== APP_VERSION) {
        console.log('init: Updating version to', APP_VERSION);
        localStorage.setItem('denoiseVisionVersion', APP_VERSION);
      }

      const savedUser = localStorage.getItem('denoiseVisionUser');
      const savedStudy = localStorage.getItem('denoiseVisionStudy');

      if (savedUser && savedStudy) {
        try {
          state.user = JSON.parse(savedUser);
          state.study = JSON.parse(savedStudy);
          console.log('init: Loaded saved session for', state.user.initials);
          updateUserInfo();
          if (state.study.currentIndex >= state.study.images.length) {
            showScreen('completion');
            updateCompletionStats();
          } else {
            showScreen('study');
            loadCurrentImage();
          }
        } catch (e) {
          console.error('init: Error parsing saved data:', e);
          showScreen('login');
        }
      } else {
        console.log('init: No saved session, showing login');
        showScreen('login');
      }
    } catch (error) {
      console.error('init: Initialization error:', error);
      showScreen('login');
    }
    setupEventListeners();
  }

  // Set up event listeners
  function setupEventListeners() {
    console.log('setupEventListeners: Attaching listeners');
    if (elements.loginForm) {
      elements.loginForm.addEventListener('submit', handleLogin);
    }
    if (elements.beginStudyBtn) {
      elements.beginStudyBtn.addEventListener('click', () => {
        showScreen('study');
        loadCurrentImage();
      });
    }
    if (elements.ratingForm) {
      elements.ratingForm.addEventListener('submit', handleRatingSubmit);
    }
    if (elements.saveProgressBtn) {
      elements.saveProgressBtn.addEventListener('click', () => {
        saveProgress();
        alert('Progress saved!');
      });
    }
    if (elements.downloadResultsBtn) {
      elements.downloadResultsBtn.addEventListener('click', downloadResultsCSV);
    }
    if (elements.startNewBtn) {
      elements.startNewBtn.addEventListener('click', () => {
        if (confirm('Start a new session?')) resetSession();
      });
    }
    if (elements.currentImage) {
      elements.currentImage.addEventListener('error', handleImageError);
    }
    const clearAllDataBtn = document.getElementById('clear-all-data-btn');
    if (clearAllDataBtn) {
      clearAllDataBtn.addEventListener('click', () => {
        if (confirm('Clear ALL saved data?')) {
          localStorage.clear();
          alert('Data cleared. Reloading...');
          location.reload();
        }
      });
    }
  }

  // Handle login
  function handleLogin(event) {
    event.preventDefault();
    console.log('handleLogin: Starting');

    const initials = elements.initialsInput?.value.trim().toUpperCase() || '';
    console.log('handleLogin: Initials:', initials);

    if (!/^[A-Z]{3}$/.test(initials)) {
      alert('Please enter exactly 3 letters for your initials.');
      console.log('handleLogin: Invalid initials');
      return;
    }

    const savedStudyKey = `denoiseVision_${initials}`;
    const savedStudy = localStorage.getItem(savedStudyKey);

    if (savedStudy) {
      try {
        state.study = JSON.parse(savedStudy);
        console.log('handleLogin: Found saved study');
        const resume = confirm(`Resume saved progress for ${initials}? (Cancel for new session)`);
        if (resume) {
          state.user = { initials };
          localStorage.setItem('denoiseVisionUser', JSON.stringify(state.user));
          localStorage.setItem('denoiseVisionStudy', JSON.stringify(state.study));
          updateUserInfo();
          if (state.study.currentIndex >= state.study.images.length) {
            showScreen('completion');
            updateCompletionStats();
          } else {
            showScreen('study');
            loadCurrentImage();
          }
          return;
        } else if (confirm(`Clear previous data for ${initials}?`)) {
          localStorage.removeItem(savedStudyKey);
        }
      } catch (error) {
        console.error('handleLogin: Error parsing saved study:', error);
        localStorage.removeItem(savedStudyKey);
      }
    }

    console.log('handleLogin: Starting new study');
    startNewStudy(initials);
  }

  // Start new study
  function startNewStudy(initials) {
    console.log('startNewStudy: Initials:', initials);
    state.user = { initials };
    try {
      localStorage.setItem('denoiseVisionUser', JSON.stringify(state.user));
    } catch (e) {
      console.error('startNewStudy: Error saving user:', e);
    }

    const images = generateImageList();
    state.study = {
      startTime: new Date().toISOString(),
      currentIndex: 0,
      images,
      results: []
    };

    try {
      const studyData = JSON.stringify(state.study);
      localStorage.setItem('denoiseVisionStudy', studyData);
      localStorage.setItem(`denoiseVision_${initials}`, studyData);
    } catch (e) {
      console.error('startNewStudy: Error saving study:', e);
    }

    updateUserInfo();
    showScreen('instructions');
  }

  // Generate image list
  function generateImageList() {
    let imageFilenames = [];
    const uniqueCount = STUDY_CONFIG.uniqueImages; // 10
  
    // Always use controlled number of images, even with AVAILABLE_IMAGES
    if (USE_IMAGE_LIST && AVAILABLE_IMAGES?.length > 0) {
      imageFilenames = [...AVAILABLE_IMAGES].slice(0, uniqueCount);
      console.log('generateImageList: Using capped AVAILABLE_IMAGES:', imageFilenames.length);
    } else {
      for (let i = 1; i <= uniqueCount; i++) {
        imageFilenames.push(`image_${i.toString().padStart(3, '0')}.jpg`);
      }
      console.log('generateImageList: Generated sequential filenames:', imageFilenames.length);
    }
  
    const images = imageFilenames.map((filename, i) => ({
      id: i + 1,
      filename,
      imageType: getRandomImageType()
    }));
  
    const duplicateCount = Math.round(images.length * (STUDY_CONFIG.duplicatePercentage / 100));
    console.log('generateImageList: Unique images:', images.length, 'Duplicate count:', duplicateCount);
  
    const duplicates = getRandomIndices(images.length, duplicateCount).map(index => ({ ...images[index] }));
    const finalImages = [...images, ...duplicates];
  
    console.log('generateImageList: Total images:', finalImages.length);
    return finalImages;
  }

  // Helper functions
  function getRandomImageType() {
    const types = ['noisy', 'original', 'denoised'];
    return types[Math.floor(Math.random() * types.length)];
  }

  function getRandomIndices(max, count) {
    const indices = new Set();
    while (indices.size < count && indices.size < max) {
      indices.add(Math.floor(Math.random() * max));
    }
    return Array.from(indices);
  }

  function updateUserInfo() {
    if (state.user && elements.userInfo && elements.userInitials) {
      elements.userInfo.classList.remove('hidden');
      elements.userInitials.textContent = state.user.initials;
    }
  }

  function showScreen(screenName) {
    console.log('showScreen:', screenName);
    Object.values(screens).forEach(screen => {
      if (screen) screen.classList.add('hidden');
    });
    if (screens[screenName]) {
      screens[screenName].classList.remove('hidden');
      state.currentScreen = screenName;
    } else {
      console.error('showScreen: Invalid screen:', screenName);
    }
  }

  function loadCurrentImage() {
    if (!state.study || state.study.currentIndex >= state.study.images.length) return;
    const currentImage = state.study.images[state.study.currentIndex];
    const totalImages = state.study.images.length;
    const progress = Math.round((state.study.currentIndex / totalImages) * 100);
    
    elements.progressFill.style.width = `${progress}%`;
    elements.progressText.textContent = `Image ${state.study.currentIndex + 1} of ${totalImages}`;
    
    elements.ratingForm.reset();
    elements.commentsText.value = '';
    
    elements.loadingImages.classList.remove('hidden');
    
    const imagePath = IMAGE_PATHS[currentImage.imageType] + currentImage.filename;
    console.log('Loading image:', { index: state.study.currentIndex + 1, imagePath });
    
    elements.currentImage.onload = () => {
      console.log('Image loaded:', imagePath);
      checkImageLoaded();
    };
    elements.currentImage.onerror = handleImageError; // Ensure this is set
    elements.currentImage.src = imagePath; // Set src last
  }

  function checkImageLoaded() {
    elements.loadingImages.classList.add('hidden');
  }

  function handleImageError(event) {
    console.error('handleImageError:', event.target.src);
    event.target.src = 'data:image/svg+xml;charset=UTF-8,%3Csvg%20width%3D%22300%22%20height%3D%22200%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Crect%20width%3D%22300%22%20height%3D%22200%22%20fill%3D%22%23fdd%22%2F%3E%3Ctext%20x%3D%22150%22%20y%3D%22100%22%20font-size%3D%2216%22%20text-anchor%3D%22middle%22%20fill%3D%22%23c00%22%3EError%20loading%20image%3C%2Ftext%3E%3C%2Fsvg%3E';
    checkImageLoaded();
  }

  function handleRatingSubmit(event) {
    event.preventDefault();
    const formData = new FormData(elements.ratingForm);
    const quality = parseInt(formData.get('quality'));
    const imageType = formData.get('imageType');
    const comments = elements.commentsText.value.trim();
    if (!quality || !imageType) {
      alert('Please complete all ratings.');
      return;
    }
    saveRating(quality, imageType, comments);
  }

  function saveRating(quality, imageType, comments) {
    const image = state.study.images[state.study.currentIndex];
    state.study.results.push({
      userId: state.user.initials,
      timestamp: new Date().toISOString(),
      imageId: image.id,
      filename: image.filename,
      actualType: image.imageType,
      perceivedQuality: quality,
      perceivedAs: imageType,
      comments,
      correctAssessment: imageType === image.imageType
    });
    state.study.currentIndex++;
    saveProgress();
    if (state.study.currentIndex >= state.study.images.length) {
      completeStudy();
    } else {
      loadCurrentImage();
    }
  }

  function saveProgress() {
    if (!state.user || !state.study) return;
    try {
      const studyData = JSON.stringify(state.study);
      localStorage.setItem('denoiseVisionStudy', studyData);
      localStorage.setItem(`denoiseVision_${state.user.initials}`, studyData);
    } catch (e) {
      console.error('saveProgress: Error:', e);
    }
  }

  async function completeStudy() {
    showScreen('completion');
    updateCompletionStats();
    await sendResultsToGoogleSheet();
  }

  function updateCompletionStats() {
    if (!state.study?.results) return;
    const results = state.study.results;
    elements.totalImages.textContent = results.length;
    const accuracy = (results.filter(r => r.correctAssessment).length / results.length * 100).toFixed(1);
    elements.accuracyRate.textContent = `${accuracy}%`;
    const avg = type => results.filter(r => r.actualType === type).reduce((sum, r) => sum + r.perceivedQuality, 0) / (results.filter(r => r.actualType === type).length || 1);
    elements.avgNoisy.textContent = avg('noisy').toFixed(1);
    elements.avgOriginal.textContent = avg('original').toFixed(1);
    elements.avgDenoised.textContent = avg('denoised').toFixed(1);
  }

  function downloadResultsCSV() {
    if (!state.study?.results?.length) {
      alert('No results to download');
      return;
    }
    const headers = ['userId', 'timestamp', 'imageId', 'filename', 'actualType', 'perceivedQuality', 'perceivedAs', 'correctAssessment', 'comments'];
    const csv = [headers.join(',')].concat(state.study.results.map(r => [
      r.userId, r.timestamp, r.imageId, r.filename, r.actualType, r.perceivedQuality, r.perceivedAs, r.correctAssessment, `"${r.comments.replace(/"/g, '""')}"`
    ].join(','))).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `denoiser_results_${state.user.initials}_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  async function sendResultsToGoogleSheet() {
    if (!state.study?.results?.length) return;
    try {
      await fetch(GOOGLE_SCRIPT_URL, {
        method: 'POST',
        mode: 'no-cors',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(state.study)
      });
      console.log('sendResultsToGoogleSheet: Sent');
    } catch (error) {
      console.error('sendResultsToGoogleSheet: Error:', error);
    }
  }

  function resetSession() {
    localStorage.removeItem('denoiseVisionUser');
    localStorage.removeItem('denoiseVisionStudy');
    if (state.user?.initials) localStorage.removeItem(`denoiseVision_${state.user.initials}`);
    state.user = null;
    state.study = null;
    elements.loginForm.reset();
    elements.ratingForm.reset();
    elements.commentsText.value = '';
    updateUserInfo();
    showScreen('login');
  }

  // Start the app
  init();
});

