# File: INK_WISPS_post.py
import os
import time
import json
import logging
import requests
import dropbox
from telegram import Bot
from datetime import datetime, timedelta
from pytz import timezone, utc

class DropboxToInstagramUploader:
    DROPBOX_TOKEN_URL = "https://api.dropbox.com/oauth2/token"
    INSTAGRAM_API_BASE = "https://graph.facebook.com/v18.0"
    INSTAGRAM_REEL_STATUS_RETRIES = 20
    INSTAGRAM_REEL_STATUS_WAIT_TIME = 5

    def __init__(self):
        self.script_name = "ink_wisps_post.py"
        self.ist = timezone('Asia/Kolkata')
        self.account_key = "eclipsed_by_you"
        self.schedule_file = "scheduler/config.json"

        # Logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()]
        )
        self.logger = logging.getLogger()

        # Secrets from GitHub environment
        self.meta_token = os.getenv("META_TOKEN")
        self.ig_id = os.getenv("IG_ID")
        self.fb_page_id = os.getenv("FB_PAGE_ID")
        
        # Telegram configuration
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        self.dropbox_key = os.getenv("DROPBOX_APP_KEY")
        self.dropbox_secret = os.getenv("DROPBOX_APP_SECRET")
        self.dropbox_refresh = os.getenv("DROPBOX_REFRESH_TOKEN")

        self.dropbox_folder = "/eclipsed_by_you"
        if self.telegram_token:
            self.telegram_bot = Bot(token=self.telegram_token)
        else:
            self.telegram_bot = None

        self.start_time = time.time()

    def send_message(self, msg, level=logging.INFO):
        prefix = f"[{self.script_name}]\n"
        full_msg = prefix + msg
        try:
            if self.telegram_bot and self.telegram_chat_id:
                self.telegram_bot.send_message(chat_id=self.telegram_chat_id, text=full_msg)
            # Also log the message to console with the specified level
            if level == logging.ERROR:
                self.logger.error(full_msg)
            else:
                self.logger.info(full_msg)
        except Exception as e:
            self.logger.error(f"Telegram send error for message '{full_msg}': {e}")

    def log_console_only(self, msg, level=logging.INFO):
        """Log message to console only, not to Telegram."""
        prefix = f"[{self.script_name}]\n"
        full_msg = prefix + msg
        if level == logging.ERROR:
            self.logger.error(full_msg)
        else:
            self.logger.info(full_msg)

    def send_token_expiry_info(self):
        try:
            debug_url = f"https://graph.facebook.com/debug_token"
            params = {
                "input_token": self.meta_token,
                "access_token": self.meta_token  # Use the same token for debugging
            }
            res = requests.get(debug_url, params=params)
            data = res.json().get("data", {})
            exp_timestamp = data.get("expires_at")

            if not exp_timestamp:
                self.send_message("⚠️ Could not retrieve token expiry info", level=logging.WARNING)
                return

            expiry_dt = datetime.fromtimestamp(exp_timestamp, tz=self.ist)
            now = datetime.now(self.ist)
            time_left = expiry_dt - now

            days = time_left.days
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes = remainder // 60

            message = (
                f"🔐 Meta Token Expiry Info:\n"
                f"📅 Expires on: {expiry_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                f"⏳ Time left: {days} days, {hours} hours, {minutes} minutes"
            )
            self.send_message(message, level=logging.INFO)

        except Exception as e:
            self.send_message(f"❌ Failed to get token expiry info: {e}", level=logging.ERROR)

    def get_page_access_token(self):
        """Fetch short-lived Page Access Token from long-lived user token."""
        try:
            self.send_message("🔐 Fetching Page Access Token from Meta API...", level=logging.INFO)
            url = f"https://graph.facebook.com/v18.0/me/accounts"
            params = {"access_token": self.meta_token}
            
            self.log_console_only(f"📡 API URL: {url}", level=logging.INFO)
            
            start_time = time.time()
            res = requests.get(url, params=params)
            request_time = time.time() - start_time
            
            self.log_console_only(f"⏱️ Page token request completed in {request_time:.2f} seconds", level=logging.INFO)
            self.log_console_only(f"📊 Response status: {res.status_code}", level=logging.INFO)

            if res.status_code != 200:
                self.send_message(f"❌ Failed to fetch Page token: {res.text}", level=logging.ERROR)
                return None

            pages = res.json().get("data", [])
            self.log_console_only(f"🔍 Found {len(pages)} pages in user account", level=logging.INFO)
            
            # Show all available pages with details (console only)
            self.log_console_only("📋 Available Pages:", level=logging.INFO)
            for i, page in enumerate(pages):
                page_id = page.get("id", "Unknown")
                page_name = page.get("name", "Unknown")
                category = page.get("category", "Unknown")
                tasks = page.get("tasks", [])
                page_access_token = page.get("access_token", "Not available")
                
                self.log_console_only(f"📄 Page {i+1}:", level=logging.INFO)
                self.log_console_only(f"   📝 Name: {page_name}", level=logging.INFO)
                self.log_console_only(f"   🆔 ID: {page_id}", level=logging.INFO)
                self.log_console_only(f"   📂 Category: {category}", level=logging.INFO)
                self.log_console_only(f"   🔧 Tasks: {', '.join(tasks)}", level=logging.INFO)
                self.log_console_only(f"   🔐 Access Token: {page_access_token[:20]}..." if page_access_token != "Not available" else "   🔐 Access Token: Not available", level=logging.INFO)
                
                # Check if this is the target page
                if page_id == self.fb_page_id:
                    self.log_console_only(f"   ✅ MATCH FOUND! This is your target page", level=logging.INFO)
                    
                    # Use the page access token directly from the response
                    if page_access_token and page_access_token != "Not available":
                        self.send_message(f"✅ Page Access Token fetched successfully for: {page_name} (ID: {self.fb_page_id})")
                        self.log_console_only(f"🔐 Using page access token: {page_access_token[:20]}...", level=logging.INFO)
                        return page_access_token
                    else:
                        self.send_message(f"❌ No access token found for page: {page_name}", level=logging.ERROR)
                        return None
                else:
                    self.log_console_only(f"   ❌ Not matching target page ID: {self.fb_page_id}", level=logging.INFO)

            # If no match found, show configuration help
            self.send_message(f"⚠️ Page ID {self.fb_page_id} not found in user's account list.", level=logging.WARNING)
            self.send_message("💡 To fix this, update your FB_PAGE_ID environment variable with one of the page IDs shown above.", level=logging.INFO)
            return None
        except Exception as e:
            self.send_message(f"❌ Exception during Page token fetch: {e}", level=logging.ERROR)
            return None

    def refresh_dropbox_token(self):
        self.logger.info("Refreshing Dropbox token...")
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.dropbox_refresh,
            "client_id": self.dropbox_key,
            "client_secret": self.dropbox_secret,
        }
        r = requests.post(self.DROPBOX_TOKEN_URL, data=data)
        if r.status_code == 200:
            new_token = r.json().get("access_token")
            self.logger.info("Dropbox token refreshed.")
            return new_token
        else:
            self.send_message("❌ Dropbox refresh failed: " + r.text)
            raise Exception("Dropbox refresh failed.")

    def list_dropbox_files(self, dbx):
        try:
            files = dbx.files_list_folder(self.dropbox_folder).entries
            valid_exts = ('.mp4', '.mov', '.jpg', '.jpeg', '.png')
            return [f for f in files if f.name.lower().endswith(valid_exts)]
        except Exception as e:
            self.send_message(f"❌ Dropbox folder read failed: {e}", level=logging.ERROR)
            return []

    def get_caption_from_config(self):
        try:
            with open(self.schedule_file, 'r') as f:
                config = json.load(f)
            
            # Get today's caption from config
            today = datetime.now(self.ist).strftime("%A")
            day_config = config.get(self.account_key, {}).get(today, {})
            
            caption = day_config.get("caption", "✨ #eclipsed_by_you ✨")
            description = day_config.get("description", caption)  # Fallback to caption if missing
            
            if not caption:
                self.send_message("⚠️ No caption found in config for today", level=logging.WARNING)
            
            return caption, description
        except Exception as e:
            self.send_message(f"❌ Failed to read caption/description from config: {e}", level=logging.ERROR)
            return "✨ #eclipsed_by_you ✨", "✨ #eclipsed_by_you ✨"

    def post_to_instagram(self, dbx, file, caption, description):
        name = file.name
        ext = name.lower()
        media_type = "REELS" if ext.endswith((".mp4", ".mov")) else "IMAGE"

        self.send_message(f"🚀 Starting upload process for: {name}", level=logging.INFO)
        
        temp_link = dbx.files_get_temporary_link(file.path_lower).link
        file_size = f"{file.size / 1024 / 1024:.2f}MB"
        total_files = len(self.list_dropbox_files(dbx))

        self.send_message(f"📸 Instagram upload details:\n📂 Type: {media_type}\n📐 Size: {file_size}\n📦 Remaining: {total_files}")

        # Get Facebook page access token for both Instagram and Facebook
        self.send_message("🔐 Step 1: Retrieving Facebook Page Access Token...", level=logging.INFO)
        page_token = self.get_page_access_token()
        if not page_token:
            self.send_message("❌ Could not retrieve Facebook Page access token. Aborting upload.", level=logging.ERROR)
            return False

        self.send_message("✅ Facebook Page Access Token retrieved successfully", level=logging.INFO)

        # Test the page token to ensure it works
        if not self.test_page_token(page_token):
            self.send_message("❌ Page token test failed. Aborting upload.", level=logging.ERROR)
            return False

        # Check if Instagram is properly connected to the Facebook page
        if not self.check_instagram_page_connection(page_token):
            self.send_message("❌ Instagram account not properly connected to Facebook page. Aborting upload.", level=logging.ERROR)
            return False

        upload_url = f"{self.INSTAGRAM_API_BASE}/{self.ig_id}/media"
        data = {
            "access_token": page_token,
            "caption": caption
        }

        if media_type == "REELS":
            data.update({"media_type": "REELS", "video_url": temp_link, "share_to_feed": "true"})
        else:
            data["image_url"] = temp_link

        self.send_message("🔄 Step 2: Sending media creation request to Instagram API...", level=logging.INFO)
        self.log_console_only(f"📡 API URL: {upload_url}", level=logging.INFO)
        
        start_time = time.time()
        res = requests.post(upload_url, data=data)
        request_time = time.time() - start_time
        
        self.log_console_only(f"⏱️ API request completed in {request_time:.2f} seconds", level=logging.INFO)
        self.log_console_only(f"📊 Response status: {res.status_code}", level=logging.INFO)
        
        if res.status_code != 200:
            err = res.json().get("error", {}).get("message", "Unknown")
            code = res.json().get("error", {}).get("code", "N/A")
            self.send_message(f"❌ Instagram upload failed: {name}\n📸 Error: {err}\n📸 Code: {code}\n📸 Status: {res.status_code}", level=logging.ERROR)
            return False

        creation_id = res.json().get("id")
        if not creation_id:
            self.send_message(f"❌ No media ID returned for: {name}", level=logging.ERROR)
            return False, media_type

        self.send_message(f"✅ Media creation successful! Creation ID: {creation_id}", level=logging.INFO)

        if media_type == "REELS":
            self.send_message("⏳ Step 3: Processing video for Instagram...", level=logging.INFO)
            processing_start = time.time()
            for attempt in range(self.INSTAGRAM_REEL_STATUS_RETRIES):
                self.log_console_only(f"🔄 Processing attempt {attempt + 1}/{self.INSTAGRAM_REEL_STATUS_RETRIES}", level=logging.INFO)
                
                status_response = requests.get(
                    f"{self.INSTAGRAM_API_BASE}/{creation_id}?fields=status_code&access_token={page_token}"
                )
                
                if status_response.status_code != 200:
                    self.send_message(f"❌ Status check failed: {status_response.status_code}", level=logging.ERROR)
                    return False
                
                status = status_response.json()
                current_status = status.get("status_code", "UNKNOWN")
                
                self.log_console_only(f"📊 Current status: {current_status}", level=logging.INFO)
                
                if current_status == "FINISHED":
                    processing_time = time.time() - processing_start
                    self.send_message(f"✅ Instagram video processing completed in {processing_time:.2f} seconds!", level=logging.INFO)
                    
                    # Wait 15 seconds after FINISHED status before publishing (official recommendation)
                    self.send_message("⏳ Waiting 15 seconds before publishing (official recommendation)...", level=logging.INFO)
                    time.sleep(15)
                    break
                elif current_status == "ERROR":
                    self.send_message(f"❌ Instagram processing failed: {name}\n📸 Status: ERROR", level=logging.ERROR)
                    return False
                
                self.log_console_only(f"⏳ Waiting {self.INSTAGRAM_REEL_STATUS_WAIT_TIME} seconds before next check...", level=logging.INFO)
                time.sleep(self.INSTAGRAM_REEL_STATUS_WAIT_TIME)

        self.send_message("📤 Step 4: Publishing to Instagram...", level=logging.INFO)
        publish_url = f"{self.INSTAGRAM_API_BASE}/{self.ig_id}/media_publish"
        publish_data = {"creation_id": creation_id, "access_token": page_token}
        
        self.log_console_only(f"📡 Publishing to: {publish_url}", level=logging.INFO)
        
        publish_start = time.time()
        pub = requests.post(publish_url, data=publish_data)
        publish_time = time.time() - publish_start
        
        self.log_console_only(f"⏱️ Publish request completed in {publish_time:.2f} seconds", level=logging.INFO)
        self.log_console_only(f"📊 Publish response status: {pub.status_code}", level=logging.INFO)
        
        # Track Instagram and Facebook results separately
        instagram_success = False
        facebook_success = False
        
        if pub.status_code == 200:
            response_data = pub.json()
            instagram_id = response_data.get("id", "Unknown")
            self.send_message(f"✅ Instagram post published successfully!\n📸 Media ID: {instagram_id}\n📸 Account ID: {self.ig_id}\n📦 Files left: {total_files - 1}")
            instagram_success = True
            
            # Verify the post is live (official recommendation)
            self.verify_instagram_post_by_creation_id(creation_id, page_token)
            
            # Also post to Facebook Page if it's a REEL (using the same page token)
            if media_type == "REELS":
                self.send_message("📘 Step 5: Starting Facebook Page upload...", level=logging.INFO)
                facebook_success = self.post_to_facebook_page(temp_link, description, page_token, instagram_id)
            else:
                facebook_success = True  # No Facebook post needed for images
            
            # Return success status for both platforms
            return True, media_type, instagram_success, facebook_success
        else:
            error_msg = pub.json().get("error", {}).get("message", "Unknown error")
            error_code = pub.json().get("error", {}).get("code", "N/A")
            self.send_message(f"❌ Instagram publish failed: {name}\n📸 Error: {error_msg}\n📸 Code: {error_code}\n📸 Status: {pub.status_code}", level=logging.ERROR)
            return False, media_type, instagram_success, facebook_success

    def crosspost_instagram_to_facebook(self, instagram_media_id, caption, page_token):
        """Crosspost Instagram video to Facebook Page instead of re-uploading."""
        try:
            self.send_message("🔄 Attempting to crosspost Instagram video to Facebook...", level=logging.INFO)
            
            # Use the crossposting endpoint
            url = f"https://graph.facebook.com/{self.fb_page_id}/feed"
            data = {
                "access_token": page_token,
                "message": caption,
                "attached_media": json.dumps([{"media_fbid": instagram_media_id}])
            }
            
            self.log_console_only(f"📡 Crosspost URL: {url}", level=logging.INFO)
            self.log_console_only(f"📸 Instagram Media ID: {instagram_media_id}", level=logging.INFO)
            
            start_time = time.time()
            res = requests.post(url, data=data)
            request_time = time.time() - start_time
            
            self.log_console_only(f"⏱️ Crosspost request completed in {request_time:.2f} seconds", level=logging.INFO)
            self.log_console_only(f"📊 Crosspost response status: {res.status_code}", level=logging.INFO)
            
            if res.status_code == 200:
                response_data = res.json()
                post_id = response_data.get("id", "Unknown")
                self.send_message(f"✅ Instagram video crossposted to Facebook successfully!\n📘 Post ID: {post_id}\n📘 Page ID: {self.fb_page_id}")
                
                # Verify the crosspost is live
                self.verify_facebook_post_by_video_id(post_id, page_token)
                return True
            else:
                error_msg = res.json().get("error", {}).get("message", "Unknown error")
                error_code = res.json().get("error", {}).get("code", "N/A")
                self.log_console_only(f"❌ Crosspost failed: {error_msg} (Code: {error_code})", level=logging.INFO)
                return False
                
        except Exception as e:
            self.log_console_only(f"❌ Exception during crosspost: {e}", level=logging.INFO)
            return False

    def post_to_facebook_page(self, video_url, caption, page_token=None, instagram_media_id=None):
        """Publish the Reel video also to the Facebook Page."""
        if not self.fb_page_id:
            self.send_message("⚠️ Facebook Page ID not configured, skipping Facebook post", level=logging.WARNING)
            return False
            
        self.send_message("📘 Starting Facebook Page upload...", level=logging.INFO)
        
        # Use the page token passed from Instagram upload, or fetch a new one
        if not page_token:
            self.send_message("🔐 Fetching fresh Facebook Page Access Token...", level=logging.INFO)
            page_token = self.get_page_access_token()
            if not page_token:
                self.send_message("❌ Could not retrieve Facebook Page access token. Aborting Facebook upload.", level=logging.ERROR)
                return False
        else:
            self.send_message("🔐 Using shared Facebook Page Access Token for Facebook upload", level=logging.INFO)

        # Try crossposting first if we have Instagram media ID
        if instagram_media_id:
            self.send_message("🔄 Attempting crosspost from Instagram to Facebook...", level=logging.INFO)
            if self.crosspost_instagram_to_facebook(instagram_media_id, caption, page_token):
                return True
            else:
                self.send_message("⚠️ Crosspost failed, falling back to direct upload...", level=logging.WARNING)

        # Fallback to direct video upload
        self.send_message("🔄 Using direct video upload to Facebook...", level=logging.INFO)

        post_url = f"https://graph.facebook.com/{self.fb_page_id}/videos"
        data = {
            "access_token": page_token,
            "file_url": video_url,
            "description": caption
        }
        
        # Debug: Show which token is being used
        self.log_console_only(f"🔐 Using page token for Facebook upload: {page_token[:20]}...", level=logging.INFO)
        self.log_console_only(f"📄 Page ID for upload: {self.fb_page_id}", level=logging.INFO)
        self.log_console_only(f"📹 Video URL: {video_url[:50]}...", level=logging.INFO)
        self.log_console_only(f"📝 Caption: {caption[:50]}...", level=logging.INFO)
        
        # Skip token verification to avoid potential issues
        self.log_console_only("🔄 Skipping token verification for Facebook upload...", level=logging.INFO)
        
        try:
            self.send_message("🔄 Sending request to Facebook API...", level=logging.INFO)
            self.log_console_only(f"📡 Facebook API URL: {post_url}", level=logging.INFO)
            
            start_time = time.time()
            res = requests.post(post_url, data=data)
            request_time = time.time() - start_time
            
            self.log_console_only(f"⏱️ Facebook API request completed in {request_time:.2f} seconds", level=logging.INFO)
            self.log_console_only(f"📊 Facebook response status: {res.status_code}", level=logging.INFO)
            
            # Log the full response for debugging (console only)
            try:
                response_json = res.json()
                self.log_console_only(f"📄 Facebook response: {json.dumps(response_json, indent=2)}", level=logging.INFO)
            except:
                self.log_console_only(f"📄 Facebook response text: {res.text}", level=logging.INFO)
            
            if res.status_code == 200:
                response_data = res.json()
                video_id = response_data.get("id", "Unknown")
                self.send_message(f"✅ Facebook Page post published successfully!\n📘 Video ID: {video_id}\n📘 Page ID: {self.fb_page_id}")
                
                # Verify the video post is live
                self.verify_facebook_post_by_video_id(video_id, page_token)
                return True
            else:
                error_msg = res.json().get("error", {}).get("message", "Unknown error")
                error_code = res.json().get("error", {}).get("code", "N/A")
                error_subcode = res.json().get("error", {}).get("error_subcode", "N/A")
                error_type = res.json().get("error", {}).get("type", "N/A")
                
                self.send_message(f"❌ Facebook Page upload failed:", level=logging.ERROR)
                self.send_message(f"📘 Error: {error_msg}", level=logging.ERROR)
                self.send_message(f"📘 Code: {error_code}", level=logging.ERROR)
                self.send_message(f"📘 Subcode: {error_subcode}", level=logging.ERROR)
                self.send_message(f"📘 Type: {error_type}", level=logging.ERROR)
                self.send_message(f"📘 Status: {res.status_code}", level=logging.ERROR)
                
                # Don't let Facebook failure affect Instagram success
                self.send_message("⚠️ Facebook upload failed, but Instagram upload was successful", level=logging.WARNING)
                return False
        except Exception as e:
            self.send_message(f"❌ Facebook Page upload exception:\n📘 Error: {str(e)}", level=logging.ERROR)
            # Don't let Facebook failure affect Instagram success
            self.send_message("⚠️ Facebook upload exception, but Instagram upload was successful", level=logging.WARNING)
            return False

    def authenticate_dropbox(self):
        """Authenticate with Dropbox and return the client."""
        try:
            access_token = self.refresh_dropbox_token()
            return dropbox.Dropbox(oauth2_access_token=access_token)
        except Exception as e:
            self.send_message(f"❌ Dropbox authentication failed: {str(e)}", level=logging.ERROR)
            raise

    def process_files_with_retries(self, dbx, caption, description, max_retries=1):
        files = self.list_dropbox_files(dbx)
        if not files:
            self.send_message("📭 No files found in Dropbox folder.", level=logging.INFO)
            return False

        # Process only the first file - no retries
        file = files[0]
        self.send_message(f"🎯 Processing single file: {file.name}", level=logging.INFO)
        
        try:
            result = self.post_to_instagram(dbx, file, caption, description)
            if isinstance(result, tuple):
                if len(result) == 4:
                    success, media_type, instagram_success, facebook_success = result
                elif len(result) == 2:
                    success, media_type = result
                    instagram_success = success
                    facebook_success = False
                else:
                    success = result
                    media_type = None
                    instagram_success = success
                    facebook_success = False
            else:
                success = result
                media_type = None
                instagram_success = success
                facebook_success = False
        except Exception as e:
            self.send_message(f"❌ Exception during post for {file.name}: {e}", level=logging.ERROR)
            success = False
            media_type = None
            instagram_success = False
            facebook_success = False

        # Always delete the file after an attempt
        try:
            dbx.files_delete_v2(file.path_lower)
            self.send_message(f"🗑️ Deleted file after attempt: {file.name}")
        except Exception as e:
            self.send_message(f"⚠️ Failed to delete file {file.name}: {e}", level=logging.WARNING)

        # Report results for each platform separately
        if instagram_success:
            if media_type == "REELS":
                self.send_message("✅ Successfully posted one reel to Instagram", level=logging.INFO)
            elif media_type == "IMAGE":
                self.send_message("✅ Successfully posted one image to Instagram", level=logging.INFO)
            else:
                self.send_message("✅ Successfully posted to Instagram", level=logging.INFO)
        else:
            self.send_message("❌ Instagram post failed", level=logging.ERROR)
            
        if media_type == "REELS":
            if facebook_success:
                self.send_message("✅ Successfully posted one reel to Facebook Page", level=logging.INFO)
            else:
                self.send_message("❌ Facebook Page post failed", level=logging.ERROR)
        
        # Final summary
        if media_type == "REELS":
            self.send_message(f"📊 Final Status: Instagram {'✅' if instagram_success else '❌'} | Facebook {'✅' if facebook_success else '❌'}", level=logging.INFO)
        else:
            self.send_message(f"📊 Final Status: Instagram {'✅' if instagram_success else '❌'} | Facebook N/A (image)", level=logging.INFO)
        
        # Return overall success (Instagram success is primary)
        return instagram_success

    def run(self):
        """Main execution method that orchestrates the posting process."""
        self.send_message(f"📡 Run started at: {datetime.now(self.ist).strftime('%Y-%m-%d %H:%M:%S')}", level=logging.INFO)
        
        try:
            # Check token expiry first
            token_valid = self.check_token_expiry()
            if not token_valid:
                self.send_message("❌ Token validation failed. Stopping execution.", level=logging.ERROR)
                return
            
            # List available pages for configuration help
            self.list_available_pages()
            
            # Get caption from config
            caption, description = self.get_caption_from_config()
            
            # Authenticate with Dropbox
            dbx = self.authenticate_dropbox()
            
            # Try posting one file only
            success = self.process_files_with_retries(dbx, caption, description, max_retries=1)
            
            if success:
                self.send_message("🎉 Instagram post completed successfully!", level=logging.INFO)
                self.send_message("📊 Summary: Instagram ✅ | Facebook status reported separately above", level=logging.INFO)
            else:
                self.send_message("❌ Instagram post failed.", level=logging.ERROR)
            
        except Exception as e:
            self.send_message(f"❌ Script crashed:\n{str(e)}", level=logging.ERROR)
            raise
        finally:
            # Send token expiry info before completion
            self.send_token_expiry_info()
            duration = time.time() - self.start_time
            self.send_message(f"🏁 Run complete in {duration:.1f} seconds", level=logging.INFO)

    def check_token_expiry(self):
        """Check Meta token expiry and send Telegram notification."""
        try:
            # Check token validity using Facebook Graph API
            check_url = f"https://graph.facebook.com/debug_token"
            params = {
                "input_token": self.meta_token,
                "access_token": self.meta_token
            }
            
            self.send_message("🔐 Checking Meta token validity...", level=logging.INFO)
            response = requests.get(check_url, params=params)
            
            if response.status_code == 200:
                fb_response = response.json()
                
                if 'data' in fb_response and 'is_valid' in fb_response['data']:
                    data = fb_response['data']
                    is_valid = data['is_valid']
                    expires_at = data.get('expires_at', 0)

                    if expires_at:
                        expiry_date = datetime.utcfromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S UTC')
                    else:
                        expiry_date = 'Never (Long-Lived Token or Page Token)'

                    message = f"🔐 Token Valid: {is_valid}\n⏳ Expires: {expiry_date}"
                    
                    if not is_valid:
                        message += "\n⚠️ WARNING: Token is invalid!"
                        self.send_message(message, level=logging.ERROR)
                    else:
                        self.send_message(message, level=logging.INFO)
                        
                    return is_valid
                else:
                    message = f"❌ Error validating token:\n{fb_response}"
                    self.send_message(message, level=logging.ERROR)
                    return False
            else:
                message = f"❌ Failed to check token: {response.status_code} - {response.text}"
                self.send_message(message, level=logging.ERROR)
                return False
                
        except Exception as e:
            message = f"❌ Exception checking token: {str(e)}"
            self.send_message(message, level=logging.ERROR)
            return False

    def check_page_permissions(self, page_token):
        """Check what permissions the page access token has."""
        try:
            self.send_message("🔍 Checking page permissions...", level=logging.INFO)
            url = f"https://graph.facebook.com/v18.0/me/permissions"
            params = {"access_token": page_token}
            
            self.send_message(f"📡 Permission check URL: {url}", level=logging.INFO)
            
            res = requests.get(url, params=params)
            self.send_message(f"📊 Permission check response status: {res.status_code}", level=logging.INFO)
            
            if res.status_code == 200:
                permissions = res.json().get("data", [])
                self.send_message(f"📋 Found {len(permissions)} permissions:", level=logging.INFO)
                
                for perm in permissions:
                    permission_name = perm.get("permission", "Unknown")
                    status = perm.get("status", "Unknown")
                    self.send_message(f"🔑 {permission_name}: {status}", level=logging.INFO)
                
                # Check for specific permissions needed for video upload
                has_publish_video = any(p.get("permission") == "publish_video" and p.get("status") == "granted" for p in permissions)
                has_publish_actions = any(p.get("permission") == "publish_actions" and p.get("status") == "granted" for p in permissions)
                has_manage_pages = any(p.get("permission") == "manage_pages" and p.get("status") == "granted" for p in permissions)
                has_pages_show_list = any(p.get("permission") == "pages_show_list" and p.get("status") == "granted" for p in permissions)
                
                self.send_message("📊 Permission Analysis:", level=logging.INFO)
                self.send_message(f"   🎥 publish_video: {'✅' if has_publish_video else '❌'}", level=logging.INFO)
                self.send_message(f"   📝 publish_actions: {'✅' if has_publish_actions else '❌'}", level=logging.INFO)
                self.send_message(f"   ⚙️ manage_pages: {'✅' if has_manage_pages else '❌'}", level=logging.INFO)
                self.send_message(f"   📋 pages_show_list: {'✅' if has_pages_show_list else '❌'}", level=logging.INFO)
                
                if not has_publish_video:
                    self.send_message("⚠️ Missing 'publish_video' permission! This is required for video uploads.", level=logging.WARNING)
                if not has_publish_actions:
                    self.send_message("⚠️ Missing 'publish_actions' permission! This is required for content publishing.", level=logging.WARNING)
                if not has_manage_pages:
                    self.send_message("⚠️ Missing 'manage_pages' permission! This is required for page management.", level=logging.WARNING)
                
                # For Facebook video uploads, we need publish_video
                if has_publish_video and has_publish_actions:
                    self.send_message("✅ Page has all required permissions for video publishing!", level=logging.INFO)
                    return True
                else:
                    self.send_message("❌ Page missing required permissions for video publishing", level=logging.ERROR)
                    return False
            else:
                error_response = res.text
                self.send_message(f"❌ Failed to check permissions: {res.status_code}", level=logging.ERROR)
                self.send_message(f"📄 Error response: {error_response}", level=logging.ERROR)
                
                # If permission check fails, let's try a different approach
                self.send_message("🔄 Trying alternative permission check...", level=logging.INFO)
                return self.check_page_permissions_alternative(page_token)
                
        except Exception as e:
            self.send_message(f"❌ Exception checking permissions: {e}", level=logging.ERROR)
            return False

    def check_page_permissions_alternative(self, page_token):
        """Alternative method to check page permissions using page info."""
        try:
            self.send_message("🔍 Alternative permission check using page info...", level=logging.INFO)
            
            # Try to get page info and check if it has video publishing capabilities
            url = f"https://graph.facebook.com/v18.0/{self.fb_page_id}"
            params = {
                "fields": "id,name,category,fan_count,verification_status,connected_instagram_account",
                "access_token": page_token
            }
            
            self.send_message(f"📡 Alternative check URL: {url}", level=logging.INFO)
            
            res = requests.get(url, params=params)
            if res.status_code == 200:
                page_info = res.json()
                page_name = page_info.get("name", "Unknown")
                page_category = page_info.get("category", "Unknown")
                
                self.send_message(f"✅ Alternative check successful!", level=logging.INFO)
                self.send_message(f"📄 Page Name: {page_name}", level=logging.INFO)
                self.send_message(f"📄 Page Category: {page_category}", level=logging.INFO)
                
                # Since we can access the page info, the token has basic permissions
                # Let's assume it can publish videos (we'll find out when we try)
                self.send_message("✅ Assuming page has video publishing permissions (will test during upload)", level=logging.INFO)
                return True
            else:
                self.send_message(f"❌ Alternative check also failed: {res.status_code}", level=logging.ERROR)
                return False
                
        except Exception as e:
            self.send_message(f"❌ Exception in alternative permission check: {e}", level=logging.ERROR)
            return False

    def refresh_page_access_token(self, page_token):
        """Refresh the page access token if it's expired."""
        try:
            self.send_message("🔄 Refreshing page access token...", level=logging.INFO)
            url = f"https://graph.facebook.com/v18.0/oauth/access_token"
            params = {
                "grant_type": "fb_exchange_token",
                "client_id": self.dropbox_key,  # Using app ID
                "client_secret": self.dropbox_secret,  # Using app secret
                "fb_exchange_token": page_token
            }
            
            res = requests.get(url, params=params)
            if res.status_code == 200:
                new_token = res.json().get("access_token")
                expires_in = res.json().get("expires_in", "Unknown")
                self.send_message(f"✅ Page access token refreshed successfully! Expires in: {expires_in} seconds")
                return new_token
            else:
                self.send_message(f"❌ Failed to refresh page token: {res.text}", level=logging.ERROR)
                return None
        except Exception as e:
            self.send_message(f"❌ Exception refreshing page token: {e}", level=logging.ERROR)
            return None

    def list_available_pages(self):
        """List all available pages for the user to help with configuration."""
        try:
            self.log_console_only("🔍 Listing all available pages for configuration...", level=logging.INFO)
            url = f"https://graph.facebook.com/v18.0/me/accounts"
            params = {"access_token": self.meta_token}
            
            res = requests.get(url, params=params)
            if res.status_code != 200:
                self.send_message(f"❌ Failed to fetch pages: {res.text}", level=logging.ERROR)
                return

            pages = res.json().get("data", [])
            self.log_console_only(f"📋 Found {len(pages)} pages:", level=logging.INFO)
            
            for i, page in enumerate(pages):
                page_id = page.get("id", "Unknown")
                page_name = page.get("name", "Unknown")
                category = page.get("category", "Unknown")
                tasks = page.get("tasks", [])
                
                self.log_console_only(f"📄 Page {i+1}:", level=logging.INFO)
                self.log_console_only(f"   📝 Name: {page_name}", level=logging.INFO)
                self.log_console_only(f"   🆔 ID: {page_id}", level=logging.INFO)
                self.log_console_only(f"   📂 Category: {category}", level=logging.INFO)
                self.log_console_only(f"   🔧 Tasks: {', '.join(tasks)}", level=logging.INFO)
                
                # Check if this matches current configuration
                if page_id == self.fb_page_id:
                    self.log_console_only(f"   ✅ CURRENTLY CONFIGURED", level=logging.INFO)
                else:
                    self.log_console_only(f"   ⚙️ To use this page, set FB_PAGE_ID={page_id}", level=logging.INFO)
            
            self.log_console_only("💡 Copy the ID of the page you want to use and set it as FB_PAGE_ID environment variable.", level=logging.INFO)
            
        except Exception as e:
            self.send_message(f"❌ Exception listing pages: {e}", level=logging.ERROR)

    def exchange_user_token_for_page_token(self, page_id):
        """Exchange user access token for page access token."""
        try:
            self.send_message(f"🔄 Exchanging token for page ID: {page_id}", level=logging.INFO)
            
            # Use the page token endpoint to get the actual page access token
            # This is the correct way to get a page access token
            url = f"https://graph.facebook.com/v18.0/{page_id}"
            params = {
                "fields": "access_token",
                "access_token": self.meta_token
            }
            
            self.send_message(f"📡 Exchange API URL: {url}", level=logging.INFO)
            self.send_message(f"🔑 Using user token to get page token for page: {page_id}", level=logging.INFO)
            
            start_time = time.time()
            res = requests.get(url, params=params)
            request_time = time.time() - start_time
            
            self.send_message(f"⏱️ Token exchange completed in {request_time:.2f} seconds", level=logging.INFO)
            self.send_message(f"📊 Exchange response status: {res.status_code}", level=logging.INFO)
            
            if res.status_code == 200:
                response_data = res.json()
                page_token = response_data.get("access_token")
                
                if page_token:
                    self.send_message("✅ Page access token obtained successfully!")
                    self.send_message(f"🔐 Page token starts with: {page_token[:20]}...", level=logging.INFO)
                    return page_token
                else:
                    self.send_message("❌ No access_token in response", level=logging.ERROR)
                    self.send_message(f"📄 Response data: {response_data}", level=logging.ERROR)
                    return None
            else:
                self.send_message(f"❌ Token exchange failed: {res.text}", level=logging.ERROR)
                return None
                
        except Exception as e:
            self.send_message(f"❌ Exception during token exchange: {e}", level=logging.ERROR)
            return None

    def check_instagram_page_connection(self, page_token):
        """Check if Instagram account is properly connected to the Facebook page."""
        try:
            self.log_console_only("🔍 Checking Instagram-Facebook page connection...", level=logging.INFO)
            
            # Check if the page has Instagram account connected
            url = f"https://graph.facebook.com/v18.0/{self.fb_page_id}"
            params = {
                "fields": "instagram_business_account,connected_instagram_account",
                "access_token": page_token
            }
            
            self.log_console_only(f"📡 Checking page Instagram connection: {url}", level=logging.INFO)
            
            res = requests.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                instagram_business_account = data.get("instagram_business_account", {})
                connected_instagram = data.get("connected_instagram_account", {})
                
                if instagram_business_account:
                    instagram_id = instagram_business_account.get("id", "Unknown")
                    self.send_message(f"✅ Instagram Business Account connected: {instagram_id}", level=logging.INFO)
                    
                    # Verify this matches our configured IG_ID
                    if instagram_id == self.ig_id:
                        self.log_console_only("✅ Instagram ID matches configured IG_ID", level=logging.INFO)
                        return True
                    else:
                        self.send_message(f"⚠️ Instagram ID mismatch! Configured: {self.ig_id}, Connected: {instagram_id}", level=logging.WARNING)
                        return False
                elif connected_instagram:
                    instagram_id = connected_instagram.get("id", "Unknown")
                    self.send_message(f"✅ Instagram Account connected: {instagram_id}", level=logging.INFO)
                    return True
                else:
                    self.send_message("❌ No Instagram account connected to this Facebook page!", level=logging.ERROR)
                    return False
            else:
                self.send_message(f"❌ Failed to check Instagram connection: {res.text}", level=logging.ERROR)
                return False
                
        except Exception as e:
            self.send_message(f"❌ Exception checking Instagram connection: {e}", level=logging.ERROR)
            return False

    def test_page_token(self, page_token):
        """Test the page access token by making a simple API call."""
        try:
            self.log_console_only("🧪 Testing page access token...", level=logging.INFO)
            
            # Test the token by getting page info
            url = f"https://graph.facebook.com/v18.0/me"
            params = {
                "fields": "id,name,category",
                "access_token": page_token
            }
            
            self.log_console_only(f"📡 Testing token with: {url}", level=logging.INFO)
            
            start_time = time.time()
            res = requests.get(url, params=params)
            request_time = time.time() - start_time
            
            self.log_console_only(f"⏱️ Token test completed in {request_time:.2f} seconds", level=logging.INFO)
            self.log_console_only(f"📊 Test response status: {res.status_code}", level=logging.INFO)
            
            if res.status_code == 200:
                page_info = res.json()
                page_id = page_info.get("id", "Unknown")
                page_name = page_info.get("name", "Unknown")
                page_category = page_info.get("category", "Unknown")
                
                self.log_console_only(f"✅ Page token test successful!", level=logging.INFO)
                self.log_console_only(f"📄 Page ID: {page_id}", level=logging.INFO)
                self.log_console_only(f"📄 Page Name: {page_name}", level=logging.INFO)
                self.log_console_only(f"📄 Page Category: {page_category}", level=logging.INFO)
                
                # Verify this matches our expected page
                if page_id == self.fb_page_id:
                    self.log_console_only("✅ Page ID matches expected page!", level=logging.INFO)
                    return True
                else:
                    self.send_message(f"⚠️ Page ID mismatch! Expected: {self.fb_page_id}, Got: {page_id}", level=logging.WARNING)
                    return False
            else:
                self.send_message(f"❌ Page token test failed: {res.text}", level=logging.ERROR)
                return False
                
        except Exception as e:
            self.send_message(f"❌ Exception testing page token: {e}", level=logging.ERROR)
            return False

    def verify_token_type(self, page_token):
        """Verify if the token is a page token."""
        try:
            self.send_message("🔍 Verifying token type...", level=logging.INFO)
            
            # Check if the token is valid by making a simple API call
            url = f"https://graph.facebook.com/v18.0/me"
            params = {
                "fields": "id,name,category",
                "access_token": page_token
            }
            
            self.send_message(f"📡 Verification URL: {url}", level=logging.INFO)
            
            start_time = time.time()
            res = requests.get(url, params=params)
            request_time = time.time() - start_time
            
            self.send_message(f"⏱️ Verification completed in {request_time:.2f} seconds", level=logging.INFO)
            self.send_message(f"📊 Verification response status: {res.status_code}", level=logging.INFO)
            
            if res.status_code == 200:
                page_info = res.json()
                page_id = page_info.get("id", "Unknown")
                page_name = page_info.get("name", "Unknown")
                page_category = page_info.get("category", "Unknown")
                
                self.send_message(f"✅ Token verification successful!", level=logging.INFO)
                self.send_message(f"📄 Page ID: {page_id}", level=logging.INFO)
                self.send_message(f"📄 Page Name: {page_name}", level=logging.INFO)
                self.send_message(f"📄 Page Category: {page_category}", level=logging.INFO)
                
                # Verify this matches our expected page
                if page_id == self.fb_page_id:
                    self.send_message("✅ Page ID matches expected page!", level=logging.INFO)
                    return True
                else:
                    self.send_message(f"⚠️ Page ID mismatch! Expected: {self.fb_page_id}, Got: {page_id}", level=logging.WARNING)
                    return False
            else:
                self.send_message(f"❌ Token verification failed: {res.text}", level=logging.ERROR)
                return False
                
        except Exception as e:
            self.send_message(f"❌ Exception verifying token type: {e}", level=logging.ERROR)
            return False

    def verify_instagram_post_by_creation_id(self, creation_id, page_token):
        """Verify Instagram post is live by polling the creation_id."""
        try:
            self.send_message("🔍 Verifying Instagram post is live...", level=logging.INFO)
            
            # Poll the creation_id to get post details
            url = f"{self.INSTAGRAM_API_BASE}/{creation_id}"
            params = {
                "fields": "id,permalink_url,media_type,media_url,thumbnail_url,created_time",
                "access_token": page_token
            }
            
            self.log_console_only(f"📡 Verification URL: {url}", level=logging.INFO)
            
            # Try up to 5 times with 3-second intervals
            for attempt in range(5):
                self.log_console_only(f"🔄 Verification attempt {attempt + 1}/5", level=logging.INFO)
                
                res = requests.get(url, params=params)
                if res.status_code == 200:
                    post_data = res.json()
                    post_id = post_data.get("id", "Unknown")
                    permalink = post_data.get("permalink_url", "Not available")
                    media_type = post_data.get("media_type", "Unknown")
                    created_time = post_data.get("created_time", "Unknown")
                    
                    self.send_message(f"✅ Instagram post verified as live!", level=logging.INFO)
                    self.log_console_only(f"📸 Post ID: {post_id}", level=logging.INFO)
                    self.log_console_only(f"🔗 Permalink: {permalink}", level=logging.INFO)
                    self.log_console_only(f"📂 Media Type: {media_type}", level=logging.INFO)
                    self.log_console_only(f"⏰ Created: {created_time}", level=logging.INFO)
                    return True
                else:
                    self.log_console_only(f"❌ Verification failed (attempt {attempt + 1}): {res.status_code}", level=logging.INFO)
                    if attempt < 4:  # Don't sleep on last attempt
                        time.sleep(3)
            
            self.send_message("⚠️ Could not verify Instagram post is live", level=logging.WARNING)
            return False
            
        except Exception as e:
            self.send_message(f"❌ Exception verifying Instagram post: {e}", level=logging.ERROR)
            return False

    def verify_facebook_post_by_video_id(self, video_id, page_token):
        """Verify Facebook video post is live by polling the video_id."""
        try:
            self.send_message("🔍 Verifying Facebook video post is live...", level=logging.INFO)
            
            # Poll the video_id to get post details
            url = f"https://graph.facebook.com/{video_id}"
            params = {
                "fields": "id,permalink_url,created_time,length,title,description",
                "access_token": page_token
            }
            
            self.log_console_only(f"📡 Verification URL: {url}", level=logging.INFO)
            
            # Try up to 5 times with 3-second intervals
            for attempt in range(5):
                self.log_console_only(f"🔄 Verification attempt {attempt + 1}/5", level=logging.INFO)
                
                res = requests.get(url, params=params)
                if res.status_code == 200:
                    post_data = res.json()
                    fb_video_id = post_data.get("id", "Unknown")
                    permalink = post_data.get("permalink_url", "Not available")
                    created_time = post_data.get("created_time", "Unknown")
                    length = post_data.get("length", "Unknown")
                    
                    self.send_message(f"✅ Facebook video post verified as live!", level=logging.INFO)
                    self.log_console_only(f"📘 Video ID: {fb_video_id}", level=logging.INFO)
                    self.log_console_only(f"🔗 Permalink: {permalink}", level=logging.INFO)
                    self.log_console_only(f"⏰ Created: {created_time}", level=logging.INFO)
                    self.log_console_only(f"⏱️ Length: {length} seconds", level=logging.INFO)
                    return True
                else:
                    self.log_console_only(f"❌ Verification failed (attempt {attempt + 1}): {res.status_code}", level=logging.INFO)
                    if attempt < 4:  # Don't sleep on last attempt
                        time.sleep(3)
            
            self.send_message("⚠️ Could not verify Facebook video post is live", level=logging.WARNING)
            return False
            
        except Exception as e:
            self.send_message(f"❌ Exception verifying Facebook video post: {e}", level=logging.ERROR)
            return False

if __name__ == "__main__":
    DropboxToInstagramUploader().run()
