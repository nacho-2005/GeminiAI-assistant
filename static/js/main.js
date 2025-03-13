// Inicializar Socket.IO
const socket = io();

// Variables globales
let currentChatId = null;
let currentPlatform = null;
let contacts = {};

// Elementos del DOM
const contactsList = document.getElementById('contactsList');
const messagesContainer = document.getElementById('messagesContainer');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const currentChatName = document.getElementById('currentChatName');
const currentChatStatus = document.getElementById('currentChatStatus');

// Cargar mensajes al iniciar
window.addEventListener('DOMContentLoaded', () => {
    loadMessages();
});

// Manejar envío de mensajes
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

sendButton.addEventListener('click', sendMessage);

// Escuchar nuevos mensajes
socket.on('new_message', (data) => {
    // Actualizar la lista de contactos
    updateContact(data.chat_id, data.sender, data.message, data.timestamp);
    
    // Si es el chat actual, mostrar el mensaje
    if (currentChatId === data.chat_id) {
        appendMessage(data.message, data.timestamp, data.is_from_assistant);
    }
});

// Función para cargar mensajes
function loadMessages() {
    fetch('/messages')
        .then(response => response.json())
        .then(messages => {
            // Agrupar mensajes por chat_id
            messages.forEach(msg => {
                updateContact(msg.chat_id, msg.sender, msg.message, msg.timestamp);
            });
            
            // Renderizar contactos
            renderContacts();
        })
        .catch(error => console.error('Error al cargar mensajes:', error));
}

// Función para actualizar un contacto
function updateContact(chatId, sender, message, timestamp) {
    if (!contacts[chatId]) {
        contacts[chatId] = {
            name: sender,
            lastMessage: message,
            timestamp: timestamp,
            platform: 'WhatsApp'
        };
    } else {
        contacts[chatId].lastMessage = message;
        contacts[chatId].timestamp = timestamp;
    }
    
    // Renderizar contactos
    renderContacts();
}

// Función para renderizar contactos
function renderContacts() {
    // Ordenar contactos por timestamp (más reciente primero)
    const sortedContacts = Object.entries(contacts).sort((a, b) => {
        return new Date(b[1].timestamp) - new Date(a[1].timestamp);
    });
    
    // Limpiar lista de contactos
    contactsList.innerHTML = '';
    
    // Agregar contactos a la lista
    sortedContacts.forEach(([chatId, contact]) => {
        const contactItem = document.createElement('div');
        contactItem.className = `contact-item ${currentChatId === chatId ? 'active' : ''}`;
        contactItem.innerHTML = `
            <div class="contact-name">${contact.name}</div>
            <div class="contact-last-message">${contact.lastMessage}</div>
        `;
        
        contactItem.addEventListener('click', () => {
            selectChat(chatId, contact.name, contact.platform);
        });
        
        contactsList.appendChild(contactItem);
    });
}

// Función para seleccionar un chat
function selectChat(chatId, name, platform) {
    // Actualizar variables globales
    currentChatId = chatId;
    currentPlatform = platform;
    
    // Actualizar UI
    currentChatName.textContent = name;
    currentChatStatus.textContent = `Chat de ${platform}`;
    messageInput.disabled = false;
    sendButton.disabled = false;
    
    // Marcar como activo en la lista de contactos
    document.querySelectorAll('.contact-item').forEach(item => {
        item.classList.remove('active');
    });
    
    document.querySelectorAll('.contact-item').forEach(item => {
        if (item.querySelector('.contact-name').textContent === name) {
            item.classList.add('active');
        }
    });
    
    // Cargar mensajes del chat
    loadChatMessages(chatId);
}

// Función para cargar mensajes de un chat específico
function loadChatMessages(chatId) {
    fetch('/messages')
        .then(response => response.json())
        .then(messages => {
            // Filtrar mensajes del chat actual
            const chatMessages = messages.filter(msg => msg.chat_id === chatId);
            
            // Ordenar por timestamp (más antiguo primero)
            chatMessages.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            
            // Limpiar contenedor de mensajes
            messagesContainer.innerHTML = '';
            
            // Mostrar mensajes
            chatMessages.forEach(msg => {
                appendMessage(msg.message, msg.timestamp, msg.is_from_assistant);
            });
            
            // Scroll al final
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        })
        .catch(error => console.error('Error al cargar mensajes del chat:', error));
}

// Función para agregar un mensaje al contenedor
function appendMessage(message, timestamp, isFromAssistant) {
    const messageElement = document.createElement('div');
    messageElement.className = `message ${isFromAssistant ? 'received' : 'sent'}`;
    
    const formattedTime = formatTimestamp(timestamp);
    
    messageElement.innerHTML = `
        <div class="message-content">${message}</div>
        <div class="message-time">${formattedTime}</div>
    `;
    
    messagesContainer.appendChild(messageElement);
    
    // Scroll al final
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Función para enviar un mensaje
function sendMessage() {
    const message = messageInput.value.trim();
    
    if (!message || !currentChatId) return;
    
    // Enviar mensaje a través de Socket.IO
    socket.emit('send_message', {
        platform: currentPlatform,
        chat_id: currentChatId,
        message: message
    });
    
    // Limpiar input
    messageInput.value = '';
    
    // Mostrar mensaje enviado inmediatamente
    const timestamp = new Date().toISOString();
    appendMessage(message, timestamp, false);
    
    // Actualizar contacto
    updateContact(currentChatId, contacts[currentChatId].name, message, timestamp);
}

// Función para formatear timestamp
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
}

// Manejo de responsive
if (window.innerWidth <= 768) {
    const chatHeader = document.querySelector('.chat-header');
    const sidebar = document.querySelector('.sidebar');
    
    // Agregar botón de menú
    const menuToggle = document.createElement('div');
    menuToggle.className = 'menu-toggle';
    menuToggle.innerHTML = '<i class="bi bi-list"></i>';
    chatHeader.prepend(menuToggle);
    
    // Manejar clic en botón de menú
    menuToggle.addEventListener('click', () => {
        sidebar.classList.toggle('show');
    });
    
    // Cerrar menú al seleccionar un chat
    document.querySelectorAll('.contact-item').forEach(item => {
        item.addEventListener('click', () => {
            sidebar.classList.remove('show');
        });
    });
}