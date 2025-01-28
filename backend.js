const axios = require('axios');
const express = require('express');
const app = express();
const clientID = 'your-client-id';
const clientSecret = 'your-client-secret';
const redirectURI = 'https://kpnworld.github.io/onWhisper/dashboard.html';

app.use(express.json());

app.post('/oauth2/callback', async (req, res) => {
    const { code } = req.body;
    
    try {
        const response = await axios.post('https://discord.com/api/oauth2/token', null, {
            params: {
                client_id: clientID,
                client_secret: clientSecret,
                code,
                grant_type: 'authorization_code',
                redirect_uri: redirectURI,
                scope: 'identify guilds'
            },
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        });

        const accessToken = response.data.access_token;

        // Fetch user info from Discord API
        const userInfo = await axios.get('https://discord.com/api/v9/users/@me', {
            headers: {
                Authorization: `Bearer ${accessToken}`
            }
        });

        // Send back the user info
        res.json({
            success: true,
            username: userInfo.data.username,
            id: userInfo.data.id
        });
    } catch (error) {
        console.error(error);
        res.json({ success: false });
    }
});

app.listen(3000, () => {
    console.log('Server running on port 3000');
});
