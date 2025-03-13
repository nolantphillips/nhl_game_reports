import pandas as pd
from nhlpy import NHLClient


def time_remaining(start_time_str, end_time_str):
    # Define total period as 20 minutes (1200 seconds)
    total_period_seconds = 20 * 60

    # Helper function to convert time string to total seconds
    def convert_to_seconds(time_str):
        minutes, seconds = map(int, time_str.split(":"))
        return minutes * 60 + seconds

    # Convert start and end times to seconds
    start_time_seconds = convert_to_seconds(start_time_str)
    end_time_seconds = convert_to_seconds(end_time_str)

    # Calculate remaining time by subtracting from 1200 seconds (20 minutes)
    start_remaining = total_period_seconds - start_time_seconds
    end_remaining = total_period_seconds - end_time_seconds

    # Helper function to convert seconds back to MM:SS format
    def convert_to_time_format(seconds):
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02}:{seconds:02}"

    # Convert remaining time back to MM:SS format
    start_remaining_time = convert_to_time_format(start_remaining)
    end_remaining_time = convert_to_time_format(end_remaining)

    return start_remaining_time, end_remaining_time


def nhl_scraper(game_ids: list):

    client = NHLClient()
    shots = []
    blocks = []
    misses = []
    goals = []
    hits = []
    give_take = []
    faceoffs = []
    pens = []
    shifts = []
    players = []
    games = []
    teams = []

    conference_dict = {
        "FLA": "Eastern",
        "TOR": "Eastern",
        "TBL": "Eastern",
        "OTT": "Eastern",
        "DET": "Eastern",
        "MTL": "Eastern",
        "BOS": "Eastern",
        "BUF": "Eastern",
        "WSH": "Eastern",
        "CAR": "Eastern",
        "NJD": "Eastern",
        "CBJ": "Eastern",
        "NYR": "Eastern",
        "NYI": "Eastern",
        "PHI": "Eastern",
        "PIT": "Eastern",
        "WPG": "Western",
        "DAL": "Western",
        "MIN": "Western",
        "COL": "Western",
        "STL": "Western",
        "UTA": "Western",
        "NSH": "Western",
        "CHI": "Western",
        "VGK": "Western",
        "EDM": "Western",
        "CGY": "Western",
        "VAN": "Western",
        "ANA": "Western",
        "SEA": "Western",
        "SJS": "Western",
        "LAK": "Western",
    }

    division_dict = {
        "FLA": "Atlantic",
        "TOR": "Atlantic",
        "TBL": "Atlantic",
        "OTT": "Atlantic",
        "DET": "Atlantic",
        "MTL": "Atlantic",
        "BOS": "Atlantic",
        "BUF": "Atlantic",
        "WSH": "Metropolitan",
        "CAR": "Metropolitan",
        "NJD": "Metropolitan",
        "CBJ": "Metropolitan",
        "NYR": "Metropolitan",
        "NYI": "Metropolitan",
        "PHI": "Metropolitan",
        "PIT": "Metropolitan",
        "WPG": "Central",
        "DAL": "Central",
        "MIN": "Central",
        "COL": "Central",
        "STL": "Central",
        "UTA": "Central",
        "NSH": "Central",
        "CHI": "Central",
        "VGK": "Pacific",
        "EDM": "Pacific",
        "CGY": "Pacific",
        "VAN": "Pacific",
        "ANA": "Pacific",
        "SEA": "Pacific",
        "SJS": "Pacific",
        "LAK": "Pacific",
    }

    for game in game_ids:
        pbp = client.game_center.play_by_play(game_id=game)

        team_id_dict = {}
        home_id = pbp["homeTeam"]["id"]
        home_team = pbp["homeTeam"]["abbrev"]
        away_id = pbp["awayTeam"]["id"]
        away_team = pbp["awayTeam"]["abbrev"]
        team_id_dict[home_id] = home_team
        team_id_dict[away_id] = away_team
        h_city = pbp["homeTeam"]["placeName"]["default"]
        h_name = pbp["homeTeam"]["commonName"]["default"]
        h_conference = conference_dict[home_team]
        h_division = division_dict[home_team]
        a_city = pbp["awayTeam"]["placeName"]["default"]
        a_name = pbp["awayTeam"]["commonName"]["default"]
        a_conference = conference_dict[away_team]
        a_division = division_dict[away_team]

        if (home_id, home_team, h_city, h_name, h_conference, h_division) not in teams:
            teams.append((home_id, home_team, h_city, h_name, h_conference, h_division))

        if (
            away_id,
            away_team,
            a_city,
            a_name,
            a_conference,
            a_division,
        ) not in teams:
            teams.append((away_id, away_team, a_city, a_name, a_conference, a_division))

        box_score = client.game_center.boxscore(game)

        if "score" not in box_score["awayTeam"]:
            continue

        away_score = box_score["awayTeam"]["score"]
        home_score = box_score["homeTeam"]["score"]
        if home_score > away_score:
            winner = home_id
            loser = away_id
        else:
            winner = away_id
            loser = home_id

        games.append((game, away_id, away_score, home_id, home_score, winner, loser))

        rosters = {}
        for guy in pbp["rosterSpots"]:
            rosters[guy["playerId"]] = {
                "name": guy["firstName"]["default"] + " " + guy["lastName"]["default"],
                "position": guy["positionCode"],
                "jersey": guy["sweaterNumber"],
                "team": guy["teamId"],
            }

        shifts_list = client.game_center.shift_chart_data(game_id=game)["data"]

        for player in rosters.keys():
            if player not in players:
                name = rosters[player]["name"]
                position = rosters[player]["position"]
                players.append((player, name, position))

        for shift in shifts_list:
            start_time, end_time = time_remaining(shift["startTime"], shift["endTime"])
            player_id = shift["playerId"]
            shift_team_id = shift["teamId"]
            duration = shift["duration"]
            period = shift["period"]
            shifts.append(
                (
                    game,
                    home_id,
                    away_id,
                    shift_team_id,
                    period,
                    start_time,
                    end_time,
                    duration,
                    player_id,
                )
            )

        for play in pbp["plays"]:

            if play["typeDescKey"] in [
                "period-start",
                "period-end",
                "stoppage",
                "delayed-penalty",
                "game-end",
            ]:
                continue

            event_id = play["eventId"]
            period = play["periodDescriptor"]["number"]
            period_type = play["periodDescriptor"]["periodType"]
            time = play["timeRemaining"]

            away_goalie = play["situationCode"][0]
            away_skaters = play["situationCode"][1]
            home_skaters = play["situationCode"][2]
            home_goalie = play["situationCode"][3]

            if "details" not in play:
                continue

            event_owner = play["details"]["eventOwnerTeamId"]
            play_type = play["typeDescKey"]

            zone = play["details"]["zoneCode"]
            x = play["details"]["xCoord"]
            y = play["details"]["yCoord"]

            if "losingPlayerId" in play["details"]:
                win_player_id = play["details"]["winningPlayerId"]
                loss_player_id = play["details"]["losingPlayerId"]
                faceoffs.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        win_player_id,
                        loss_player_id,
                        x,
                        y,
                        zone,
                    )
                )
            elif "hittingPlayerId" in play["details"]:
                hitter_id = play["details"]["hittingPlayerId"]
                hittee_id = play["details"]["hitteePlayerId"]
                hits.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        hitter_id,
                        hittee_id,
                        x,
                        y,
                        zone,
                    )
                )
            elif play_type in ["takeaway", "giveaway"]:
                player_id = play["details"]["playerId"]
                give_take.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        player_id,
                        x,
                        y,
                        zone,
                    )
                )
            elif play_type == "penalty":
                penalty_type = play["details"]["descKey"]
                if "drawnByPlayerId" not in play["details"]:
                    drawer_id = None
                else:
                    drawer_id = play["details"]["drawnByPlayerId"]
                if "committedByPlayerId" not in play["details"]:
                    guilty_id = None
                else:
                    guilty_id = play["details"]["committedByPlayerId"]
                duration = play["details"]["duration"]
                pens.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        penalty_type,
                        drawer_id,
                        guilty_id,
                        duration,
                        x,
                        y,
                        zone,
                    )
                )
            elif play_type == "shot-on-goal":
                shooter_id = play["details"]["shootingPlayerId"]
                goalie_id = play["details"]["goalieInNetId"]
                shot_type = play["details"]["shotType"]
                shots.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        shot_type,
                        shooter_id,
                        goalie_id,
                        x,
                        y,
                        zone,
                    )
                )
            elif play_type == "missed-shot":
                shooter_id = play["details"]["shootingPlayerId"]
                if "goalieInNetId" not in play["details"]:
                    goalie_id = None
                else:
                    goalie_id = play["details"]["goalieInNetId"]
                shot_type = play["details"]["shotType"]
                reason = play["details"]["reason"]
                misses.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        shot_type,
                        shooter_id,
                        goalie_id,
                        reason,
                        x,
                        y,
                        zone,
                    )
                )
            elif play_type == "goal":
                shooter_id = play["details"]["scoringPlayerId"]
                if "goalieInNetId" not in play["details"]:
                    goalie_id = None
                else:
                    goalie_id = play["details"]["goalieInNetId"]
                if "shotType" not in play["details"]:
                    shot_type = None
                else:
                    shot_type = play["details"]["shotType"]
                if "assist1PlayerTotal" in play["details"]:
                    primary_assist_id = play["details"]["assist1PlayerId"]
                    if "assist2PlayerId" in play["details"]:
                        secondary_assist_id = play["details"]["assist2PlayerId"]
                    else:
                        secondary_assist_id = None
                else:
                    primary_assist_id = None
                goals.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        shot_type,
                        shooter_id,
                        goalie_id,
                        primary_assist_id,
                        secondary_assist_id,
                        x,
                        y,
                        zone,
                    )
                )
            elif "blocked-shot" == play_type:
                if "blockingPlayerId" not in play["details"]:
                    blocked_by_id = None
                else:
                    blocked_by_id = play["details"]["blockingPlayerId"]
                shooter_id = play["details"]["shootingPlayerId"]
                blocks.append(
                    (
                        game,
                        home_id,
                        home_team,
                        away_id,
                        away_team,
                        event_owner,
                        period,
                        period_type,
                        time,
                        event_id,
                        play_type,
                        away_goalie,
                        home_goalie,
                        away_skaters,
                        home_skaters,
                        blocked_by_id,
                        shooter_id,
                        x,
                        y,
                        zone,
                    )
                )
            else:
                continue

    shots_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "shot_type",
        "shooter_id",
        "goalie_id",
        "x",
        "y",
        "zone",
    ]
    blocks_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "blocked_by_id",
        "shooter_id",
        "x",
        "y",
        "zone",
    ]
    misses_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "shot_type",
        "shooter_id",
        "goalie_id",
        "reason",
        "x",
        "y",
        "zone",
    ]
    goals_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "shot_type",
        "shooter_id",
        "goalie_id",
        "primary_assist_id",
        "secondary_assist_id",
        "x",
        "y",
        "zone",
    ]
    hits_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "hitter_id",
        "hittee_id",
        "x",
        "y",
        "zone",
    ]
    give_take_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "player_id",
        "x",
        "y",
        "zone",
    ]
    faceoffs_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "win_player_id",
        "loss_player_id",
        "x",
        "y",
        "zone",
    ]
    pens_h = [
        "game",
        "home_id",
        "home_team",
        "away_id",
        "away_team",
        "event_owner",
        "period",
        "period_type",
        "time",
        "event_id",
        "play_type",
        "away_goalie",
        "home_goalie",
        "away_skaters",
        "home_skaters",
        "penalty_type",
        "drawer_id",
        "guilty_id",
        "duration",
        "x",
        "y",
        "zone",
    ]
    shifts_h = [
        "game",
        "home_id",
        "away_id",
        "shift_team",
        "period",
        "start_time",
        "end_time",
        "duration",
        "player_id",
    ]
    players_h = ["player_id", "name", "position"]
    games_h = [
        "game",
        "away_id",
        "away_score",
        "home_id",
        "home_score",
        "winner",
        "loser",
    ]
    teams_h = ["team_id", "team_abbrev", "city", "name", "conference", "division"]

    shots_df = pd.DataFrame(shots, columns=shots_h)
    blocks_df = pd.DataFrame(blocks, columns=blocks_h)
    misses_df = pd.DataFrame(misses, columns=misses_h)
    goals_df = pd.DataFrame(goals, columns=goals_h)
    hits_df = pd.DataFrame(hits, columns=hits_h)
    give_take_df = pd.DataFrame(give_take, columns=give_take_h)
    faceoffs_df = pd.DataFrame(faceoffs, columns=faceoffs_h)
    pens_df = pd.DataFrame(pens, columns=pens_h)
    shifts_df = pd.DataFrame(shifts, columns=shifts_h)
    players_df = pd.DataFrame(players, columns=players_h)
    games_df = pd.DataFrame(games, columns=games_h)
    teams_df = pd.DataFrame(teams, columns=teams_h)

    return (
        shots_df,
        blocks_df,
        misses_df,
        goals_df,
        hits_df,
        give_take_df,
        faceoffs_df,
        pens_df,
        shifts_df,
        players_df,
        games_df,
        teams_df,
    )
